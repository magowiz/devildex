"""theme manager module."""

import ast
import logging
import shutil
from pathlib import Path
from typing import Optional, Union

import yaml

from devildex.info import PROJECT_ROOT

logger = logging.getLogger(__name__)


class ThemeManager:
    """Class that implements themes."""

    def __init__(
        self,
        project_path: Path,
        doc_type: str,
        sphinx_conf_file: Union[Path | None] = None,
        mkdocs_yml_file: Union[Path | None] = None,
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
        self.new_theme_name = "devildex"
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
        ast.fix_missing_locations(tree)
        Path(conf_file).write_text(ast.unparse(tree), encoding="utf-8")

    def mkdocs_apply_customizations(
        self, temp_dir_for_themed_yml: Path
    ) -> Optional[Path]:
        """Applies DevilDex theme customizations to an MkDocs project.
        MVP: Copies mkdocs.yml to a temporary location and potentially adds `custom_dir`.
        Returns the path to the mkdocs.yml file to be used for the build.
        """
        if (
            self.doc_type != "mkdocs"
            or not self.mkdocs_yml_file
            or not self.mkdocs_yml_file.is_file()
        ):
            logger.warning(
                f"ThemeManager: Not an MkDocs project or mkdocs.yml ({self.mkdocs_yml_file}) "
                "not found/set for theming. Cannot apply customizations."
            )
            return None  # Indicate that theming couldn't be applied / use original

        logger.info(
            f"ThemeManager: Applying MkDocs customizations for {self.mkdocs_yml_file}"
        )
        themed_mkdocs_yml_path = temp_dir_for_themed_yml / "mkdocs.devildex.yml"

        try:
            with open(self.mkdocs_yml_file, encoding="utf-8") as f_in:
                config = yaml.safe_load(f_in)
                if config is None:
                    config = {}  # Handle empty YAML file

            # --- Actual Theming Logic Would Go Here ---
            # For MVP, we'll just copy and potentially add custom_dir
            # 1. Ensure your DevilDex MkDocs theme assets are in self.mkdocs_theme_assets_source_path
            # 2. Copy these assets to the source project directory, under self.mkdocs_theme_override_dir_name
            #    This allows MkDocs to find them via a relative `custom_dir`.

            mkdocs_project_actual_root = self.mkdocs_yml_file.parent
            target_theme_override_path_in_project = (
                mkdocs_project_actual_root / self.mkdocs_theme_override_dir_name
            )

            if (
                self.mkdocs_theme_assets_source_path.exists()
                and self.mkdocs_theme_assets_source_path.is_dir()
            ):
                if target_theme_override_path_in_project.exists():
                    logger.debug(
                        f"Removing existing theme override dir: {target_theme_override_path_in_project}"
                    )
                    shutil.rmtree(target_theme_override_path_in_project)
                logger.info(
                    f"Copying DevilDex MkDocs theme assets from {self.mkdocs_theme_assets_source_path} "
                    f"to {target_theme_override_path_in_project}"
                )
                shutil.copytree(
                    self.mkdocs_theme_assets_source_path,
                    target_theme_override_path_in_project,
                )

                # Modify the YAML configuration to use the custom_dir
                current_theme_config = config.get(
                    "theme", "mkdocs"
                )  # Default to 'mkdocs' theme name
                if isinstance(current_theme_config, str):
                    config["theme"] = {
                        "name": current_theme_config,
                        "custom_dir": self.mkdocs_theme_override_dir_name,
                    }
                elif isinstance(current_theme_config, dict):
                    current_theme_config["custom_dir"] = (
                        self.mkdocs_theme_override_dir_name
                    )
                    # Ensure 'name' exists if it's a dict, otherwise MkDocs might complain
                    if "name" not in current_theme_config:
                        current_theme_config["name"] = "mkdocs"  # Default theme name
                    config["theme"] = current_theme_config
                else:  # Default if 'theme' is not str or dict (e.g. None or other type)
                    config["theme"] = {
                        "name": "mkdocs",  # Default theme name
                        "custom_dir": self.mkdocs_theme_override_dir_name,
                    }
                logger.info(
                    f"ThemeManager: Added/updated 'custom_dir': '{self.mkdocs_theme_override_dir_name}' to MkDocs config."
                )
            else:
                logger.warning(
                    f"ThemeManager: DevilDex MkDocs theme assets not found at {self.mkdocs_theme_assets_source_path}. "
                    "Skipping custom_dir injection."
                )
            # --- End Theming Logic ---

            temp_dir_for_themed_yml.mkdir(parents=True, exist_ok=True)
            with open(themed_mkdocs_yml_path, "w", encoding="utf-8") as f_out:
                yaml.dump(config, f_out, sort_keys=False, default_flow_style=False)

            logger.info(
                f"ThemeManager: Wrote (potentially) themed mkdocs.yml to {themed_mkdocs_yml_path}"
            )
            return themed_mkdocs_yml_path

        except Exception:
            logger.exception(
                f"ThemeManager: Error applying MkDocs customizations to {self.mkdocs_yml_file}"
            )
            # Fallback: if theming fails, the caller might decide to use the original yml
            return None
