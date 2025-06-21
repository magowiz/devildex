"""theme manager module."""

import ast
import logging
import shutil
from pathlib import Path
from typing import Optional

import yaml

from devildex.info import PROJECT_ROOT

logger = logging.getLogger(__name__)


class ThemeManager:
    """Class that implements themes."""

    def __init__(
        self,
        project_path: Path,
        doc_type: str,
        sphinx_conf_file: Optional[Path] = None,
        mkdocs_yml_file: Optional[Path] = None,
    ) -> None:
        """Initialize ThemeManager."""
        self.project_path = project_path
        self.doc_type = doc_type
        self.sphinx_conf_file = sphinx_conf_file
        self.mkdocs_yml_file = mkdocs_yml_file
        theme_container_dir = PROJECT_ROOT / "src" / "devildex" / "theming" / "sphinx"
        self.settings = {
            "html_theme": "devildex_sphinx_theme",
            "html_theme_path": [str(theme_container_dir.resolve())],
        }
        self.potential_sphinx_conf_paths = [
            self.project_path / "conf.py",
            self.project_path / "source" / "conf.py",
            self.project_path / "docs" / "conf.py",
            self.project_path / "doc" / "conf.py",
        ]
        self.mkdocs_theme_override_dir_name = "devildex_mkdocs_theme_override"
        self.mkdocs_theme_assets_source_path = (
            PROJECT_ROOT
            / "src"
            / "devildex"
            / "theming"
            / "mkdocs"
            / self.mkdocs_theme_override_dir_name
        )

    @staticmethod
    def _get_value_from_ast(tree: ast.AST, key: str) -> str:
        """Analizza l'albero sintattico (AST) per trovare un valore.

        Args:
            tree: L'oggetto AST generato dal parsing del file conf.py.
            key: key to search

        Returns:
            Il nome del tema originale come stringa se trovato, altrimenti "unknown".

        """
        for node in ast.walk(tree):
            if (
                (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == key
                )
                and isinstance(node.value, ast.Constant)
                and isinstance(
                    node.value.value,
                    str,
                )
            ):
                return node.value.value
        return "unknown"

    @staticmethod
    def _get_list_from_ast(tree: ast.AST, key: str) -> list[str]:
        """Analizza l'albero sintattico (AST) per trovare un valore.

        Args:
            tree: L'oggetto AST generato dal parsing del file conf.py.
            key: key to search

        Returns:
            Il nome del tema originale come stringa se trovato, altrimenti "unknown".

        """
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == key
            ) and isinstance(node.value, ast.List):
                elements = []
                for element_node in node.value.elts:
                    if isinstance(element_node, ast.Constant) and isinstance(
                        element_node.value, str
                    ):
                        elements.append(element_node.value)
                return elements
        return []

    def sphinx_change_conf(self) -> None:
        """Patch sphinx configuration."""
        if self.doc_type != "sphinx":
            return
        conf_file = self.sphinx_conf_file
        if not conf_file or not conf_file.is_file():
            conf_file = next(
                (p for p in self.potential_sphinx_conf_paths if p.is_file()), None
            )
        with open(conf_file, encoding="utf-8") as f:
            source_code = f.read()
        tree = ast.parse(source_code, filename=str(conf_file))
        values_context = {
            "original_theme_name": self._get_value_from_ast(tree, "html_theme"),
            "extensions": self._get_list_from_ast(tree, "extensions"),
        }
        for var, value in self.settings.items():
            var_found = False
            for node in tree.body:
                if (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == var
                ):
                    if isinstance(value, str):
                        node.value = ast.Constant(value=value)
                        var_found = True
                        break
                    node.value = ast.List(
                        elts=[ast.Constant(value=s) for s in value], ctx=ast.Load()
                    )
                    var_found = True
                    break
            if not var_found:
                if isinstance(value, str):
                    new_assignment = ast.Assign(
                        targets=[ast.Name(id=var, ctx=ast.Store())],
                        value=ast.Constant(value=value),
                    )
                    tree.body.append(new_assignment)
                else:
                    new_assignment = ast.Assign(
                        targets=[ast.Name(id=var, ctx=ast.Store())],
                        value=ast.List(
                            elts=[ast.Constant(value=s) for s in value], ctx=ast.Load()
                        ),
                    )
                    tree.body.append(new_assignment)

        self._apply_sphinx_html_context(tree, values_context)

        ast.fix_missing_locations(tree)
        Path(conf_file).write_text(ast.unparse(tree), encoding="utf-8")

    @staticmethod
    def _apply_sphinx_html_context(tree: ast.AST, values_context: dict) -> None:
        html_context_found = False
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "html_context"
            ):
                if isinstance(node.value, ast.Dict):
                    for key_to_add, value_to_add in values_context.items():
                        node.value.keys.append(ast.Constant(value=key_to_add))
                        if isinstance(value_to_add, list):
                            list_node = ast.List(
                                elts=[ast.Constant(s) for s in value_to_add],
                                ctx=ast.Load(),
                            )
                            node.value.values.append(list_node)
                        else:
                            node.value.values.append(ast.Constant(value=value_to_add))
                html_context_found = True
                break

        if not html_context_found:
            keys_for_dict = []
            values_for_dict = []
            for key, value in values_context.items():
                keys_for_dict.append(ast.Constant(value=key))
                if isinstance(value, list):
                    list_node = ast.List(
                        elts=[ast.Constant(s) for s in value], ctx=ast.Load()
                    )
                    values_for_dict.append(list_node)
                else:
                    values_for_dict.append(ast.Constant(value=value))

            new_node = ast.Assign(
                targets=[ast.Name(id="html_context", ctx=ast.Store())],
                value=ast.Dict(keys=keys_for_dict, values=values_for_dict),
            )
            tree.body.append(new_node)

    def _load_mkdocs_config_for_theming(
        self,
    ) -> tuple[Optional[dict], Optional[Path]]:
        """Load mkdocs.yml and returns its content and parent directory."""
        try:
            with open(self.mkdocs_yml_file, encoding="utf-8") as f_in:
                config = yaml.safe_load(f_in)
                if config is None:  # Handle empty or all-comment YAML
                    config = {}
            original_yml_parent_dir = self.mkdocs_yml_file.parent
        except (yaml.YAMLError, OSError) as e:
            logger.error(
                f"ThemeManager: Error loading/parsing {self.mkdocs_yml_file}: {e}",
                exc_info=True,
            )
            return None, None
        else:
            return config, original_yml_parent_dir

    def _process_docs_dir_config(
        self, config: dict, original_yml_parent_dir: Path
    ) -> None:
        """Resolve 'docs_dir' to an absolute path in the config if relative.

        Logs errors if the path is invalid. Modifies config in-place.
        """
        original_docs_dir_value = config.get("docs_dir", "docs")
        docs_dir_path_obj_from_config = Path(original_docs_dir_value)

        if not docs_dir_path_obj_from_config.is_absolute():
            absolute_docs_dir = (
                original_yml_parent_dir / original_docs_dir_value
            ).resolve()

            if absolute_docs_dir.exists() and absolute_docs_dir.is_dir():
                config["docs_dir"] = str(absolute_docs_dir)
                logger.info(
                    "ThemeManager: Updated 'docs_dir' in temporary YAML to absolute"
                    f" path: {config['docs_dir']}"
                )
            else:
                logger.error(
                    "ThemeManager: Original 'docs_dir' "
                    f"('{original_docs_dir_value}') from {self.mkdocs_yml_file} "
                    "resolved to non-existent/non-directory"
                    f" path '{absolute_docs_dir}'. "
                    "MkDocs build is expected to fail."
                )
        elif (
            not docs_dir_path_obj_from_config.exists()
            or not docs_dir_path_obj_from_config.is_dir()
        ):
            logger.error(
                "ThemeManager: Original absolute 'docs_dir' "
                f"('{original_docs_dir_value}') from {self.mkdocs_yml_file} "
                "does not exist or is not a directory. "
                "MkDocs build will likely fail."
            )

    def _apply_theme_overrides(
        self,
        config: dict,
        mkdocs_project_actual_root: Path,
    ) -> None:
        """Copy DevilDex MkDocs theme assets and updates the 'theme' config.

        Modifies config in-place. Can raise shutil.Error or OSError.
        """
        target_theme_override_path_in_project = (
            mkdocs_project_actual_root / self.mkdocs_theme_override_dir_name
        )

        if (
            self.mkdocs_theme_assets_source_path.exists()
            and self.mkdocs_theme_assets_source_path.is_dir()
        ):
            if target_theme_override_path_in_project.exists():
                logger.debug(
                    "Removing existing theme override dir: "
                    f"{target_theme_override_path_in_project}"
                )
                shutil.rmtree(target_theme_override_path_in_project)
            logger.info(
                "Copying DevilDex MkDocs theme assets from "
                f"{self.mkdocs_theme_assets_source_path} "
                f"to {target_theme_override_path_in_project}"
            )
            shutil.copytree(
                self.mkdocs_theme_assets_source_path,
                target_theme_override_path_in_project,
            )

            current_theme_config = config.get("theme", "mkdocs")
            if isinstance(current_theme_config, str):
                config["theme"] = {
                    "name": current_theme_config,
                    "custom_dir": self.mkdocs_theme_override_dir_name,
                }
            elif isinstance(current_theme_config, dict):
                current_theme_config["custom_dir"] = self.mkdocs_theme_override_dir_name
                if "name" not in current_theme_config:
                    current_theme_config["name"] = "mkdocs"
                config["theme"] = current_theme_config
            else:
                config["theme"] = {
                    "name": "mkdocs",
                    "custom_dir": self.mkdocs_theme_override_dir_name,
                }
            logger.info(
                "ThemeManager: Added/updated 'custom_dir': "
                f"'{self.mkdocs_theme_override_dir_name}' to MkDocs config."
            )
        else:
            logger.warning(
                "ThemeManager: DevilDex MkDocs theme assets not found at"
                f" {self.mkdocs_theme_assets_source_path}. "
                "Skipping custom_dir injection."
            )

    @staticmethod
    def _save_processed_mkdocs_config(
        config: dict, temp_dir_for_themed_yml: Path
    ) -> Path:
        """Save the processed config to a temporary YAML file.

        Can raise OSError or yaml.YAMLError.
        """
        themed_mkdocs_yml_path = temp_dir_for_themed_yml / "mkdocs.devildex.yml"
        temp_dir_for_themed_yml.mkdir(parents=True, exist_ok=True)

        with open(themed_mkdocs_yml_path, "w", encoding="utf-8") as f_out:
            yaml.dump(config, f_out, sort_keys=False, default_flow_style=False)
        logger.info(
            "ThemeManager: Wrote (potentially) themed mkdocs.yml to"
            f" {themed_mkdocs_yml_path}"
        )
        return themed_mkdocs_yml_path

    def mkdocs_apply_customizations(
        self, temp_dir_for_themed_yml: Path
    ) -> Optional[Path]:
        """Apply DevilDex theme customizations to an MkDocs project.

        Reads mkdocs.yml, resolves docs_dir, copies theme assets,
        updates theme configuration, and saves to a temporary location.
        Returns the path to the mkdocs.yml file to be used for the build.
        """
        if (
            self.doc_type != "mkdocs"
            or not self.mkdocs_yml_file
            or not self.mkdocs_yml_file.is_file()
        ):
            logger.warning(
                "ThemeManager: Not an MkDocs project or mkdocs.yml "
                f"({self.mkdocs_yml_file}) "
                "not found/set for theming. Cannot apply customizations."
            )
            return None

        logger.info(
            f"ThemeManager: Applying MkDocs customizations for {self.mkdocs_yml_file}"
        )

        try:
            config, original_yml_parent_dir = self._load_mkdocs_config_for_theming()
            if config is None or original_yml_parent_dir is None:
                return None  # Error already logged by helper

            self._process_docs_dir_config(config, original_yml_parent_dir)

            mkdocs_project_actual_root = self.mkdocs_yml_file.parent
            self._apply_theme_overrides(config, mkdocs_project_actual_root)

            themed_mkdocs_yml_path = self._save_processed_mkdocs_config(
                config, temp_dir_for_themed_yml
            )
        except (yaml.YAMLError, OSError, shutil.Error):
            logger.exception(
                f"ThemeManager: Error applying MkDocs customizations "
                f"to {self.mkdocs_yml_file}"
            )
            return None
        else:
            return themed_mkdocs_yml_path
