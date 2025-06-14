"""mkdocs build module."""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import execute_command, install_environment_dependencies

logger = logging.getLogger(__name__)
MKDOCS_CONFIG_FILE = "mkdocs.yml"
BUILT_IN_MARKER = "built-in"

KNOWN_THEME_PACKAGES: dict[str, str] = {
    "material": "mkdocs-material",
}


KNOWN_PLUGIN_PACKAGES: dict[str, str | None] = {
    "mkdocstrings": "mkdocstrings[python]",
    "macros": "mkdocs-macros-plugin",
    "callouts": "mkdocs-callouts",
    "pymdownx.arithmatex": "pymdown-extensions",
    "pymdownx.betterem": "pymdown-extensions",
    "pymdownx.caret": "pymdown-extensions",
    "pymdownx.critic": "pymdown-extensions",
    "pymdownx.details": "pymdown-extensions",
    "pymdownx.emoji": "pymdown-extensions",
    "pymdownx.escapeall": "pymdown-extensions",
    "pymdownx.highlight": "pymdown-extensions",
    "pymdownx.inlinehilite": "pymdown-extensions",
    "pymdownx.keys": "pymdown-extensions",
    "pymdownx.mark": "pymdown-extensions",
    "pymdownx.magiclink": "pymdown-extensions",
    "pymdownx.progressbar": "pymdown-extensions",
    "pymdownx.smartsymbols": "pymdown-extensions",
    "pymdownx.striphtml": "pymdown-extensions",
    "pymdownx.superfences": "pymdown-extensions",
    "pymdownx.tabbed": "pymdown-extensions",
    "pymdownx.tasklist": "pymdown-extensions",
    "pymdownx.tilde": "pymdown-extensions",
    "pymdownx.snippets": "pymdown-extensions",
    "mkdocs-section-index": "mkdocs-section-index",
    "codehilite": "Pygments",
    "search": BUILT_IN_MARKER,
    "toc": BUILT_IN_MARKER,
    "admonition": BUILT_IN_MARKER,
    "attr_list": BUILT_IN_MARKER,
    "md_in_html": BUILT_IN_MARKER,
    "footnotes": BUILT_IN_MARKER,
    "tables": BUILT_IN_MARKER,
    "def_list": BUILT_IN_MARKER,
    "autorefs": "mkdocs-autorefs",
    "literate-nav": "mkdocs-literate-nav",
    "mkdocs-click": "mkdocs-click",
    "redirects": "mkdocs-redirects",
}


@dataclass
class MkDocsBuildContext:
    """Holds context for an MkDocs build operation."""

    config_content: Optional[dict]
    project_root: Path
    original_yml_path: Path
    final_output_dir: Path
    project_slug: str
    processed_yml_path: Path


def _preprocess_mkdocs_config(
    original_config_content: Optional[dict],
) -> tuple[Optional[dict], bool]:
    """Preprocess the MkDocs config content.

    Currently, it moves 'callouts' from 'markdown_extensions' to 'plugins'.
    Operates on a copy of the input dictionary.

    Args:
        original_config_content: The parsed content of the original mkdocs.yml.

    Returns:
        A tuple: (processed_config_content, was_modified_boolean).
        Returns (None, False) if original_config_content is None.

    """
    if not original_config_content:
        return None, False

    processed_config = original_config_content.copy()
    config_modified = False
    callouts_value_to_move = None

    if "markdown_extensions" in processed_config:
        md_exts = processed_config["markdown_extensions"]
        new_md_exts = []
        found_in_ext = False
        if isinstance(md_exts, list):
            for ext_item in md_exts:
                if isinstance(ext_item, str) and ext_item == "callouts":
                    callouts_value_to_move = "callouts"
                    found_in_ext = True
                elif isinstance(ext_item, dict) and "callouts" in ext_item:
                    callouts_value_to_move = ext_item.copy()
                    found_in_ext = True
                else:
                    new_md_exts.append(ext_item)
            if found_in_ext:
                processed_config["markdown_extensions"] = new_md_exts
                config_modified = True
                logger.info("Rimosso 'callouts' da 'markdown_extensions' (lista).")
        elif isinstance(md_exts, dict) and "callouts" in md_exts:  # Meno comune
            callouts_value_to_move = {"callouts": md_exts.pop("callouts")}
            config_modified = True
            logger.info("Rimosso 'callouts' da 'markdown_extensions' (dict).")

    # Se 'callouts' è stato trovato e rimosso, aggiungilo a 'plugins'
    if callouts_value_to_move:
        plugins_list = processed_config.get("plugins", [])
        if not isinstance(plugins_list, list):
            logger.warning(
                f"'plugins' in mkdocs.yml era {type(plugins_list)}, non una lista. "
                "Inizializzo come nuova lista."
            )
            plugins_list = []

        already_is_plugin = False
        for plugin_item in plugins_list:
            if isinstance(plugin_item, str) and plugin_item == "callouts":
                already_is_plugin = True
                break
            if isinstance(plugin_item, dict) and "callouts" in plugin_item:
                already_is_plugin = True
                break

        if not already_is_plugin:
            plugins_list.append(callouts_value_to_move)
            processed_config["plugins"] = plugins_list
            config_modified = True
            logger.info(f"Aggiunto '{callouts_value_to_move}' a 'plugins'.")
        else:
            logger.info(
                f"'{callouts_value_to_move}' già presente in 'plugins'. Nessuna aggiunta."
            )

    return processed_config, config_modified


def _find_mkdocs_config_file(project_root_path: Path) -> Optional[Path]:
    """Find the mkdocs.yml file, typically at the project root."""
    mkdocs_conf = project_root_path / MKDOCS_CONFIG_FILE
    if mkdocs_conf.is_file():
        logger.info(f"Found Mkdocs Config file:{mkdocs_conf}")
        return mkdocs_conf
    logger.warning(
        f"Mkdocs Config Not Found at{mkdocs_conf}. Searching in 'docs' subdir ..."
    )
    mkdocs_conf_in_docs = project_root_path / "docs" / MKDOCS_CONFIG_FILE
    if mkdocs_conf_in_docs.is_file():
        logger.info(f"Found Mkdocs Config files in Docs/ Subdir:{mkdocs_conf_in_docs}")
        return mkdocs_conf_in_docs
    logger.error(f"Mkdocs Confront Found Found in{project_root_path}Now 'docs' subdir.")
    return None


def _parse_mkdocs_config(config_file_path: Path) -> Optional[dict]:
    """Perform the parsing of the mkdocs.yml file."""
    try:
        with open(config_file_path, encoding="utf-8") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        logger.info(f"Successfully parsed MkDocs Config: {config_file_path}")
    except yaml.YAMLError:
        logger.exception(
            f"Error parsing MkDocs Config file: {config_file_path}"
        )  # Log corretto
    except OSError:
        logger.exception(f"Error reading MkDocs Config file: {config_file_path}")
    else:
        return config
    return None


def _get_theme_packages_to_install(
    theme_config: Optional[Union[str, dict[str, Any]]],
) -> list[str]:
    """Determine the PIP packages needed based on the theme configuration."""
    theme_packages: list[str] = []
    theme_name_to_check: Optional[str] = None
    if isinstance(theme_config, str):
        theme_name_to_check = theme_config
    elif isinstance(theme_config, dict):
        theme_name_to_check = theme_config.get("name")
    if theme_name_to_check and theme_name_to_check not in ["mkdocs", "readthedocs"]:
        package = KNOWN_THEME_PACKAGES.get(theme_name_to_check)
        if package:
            theme_packages.append(package)
            logger.debug(
                f"Identified Theme Package for '{theme_name_to_check}': {package}"
            )
        else:
            logger.debug(
                f"Theme '{theme_name_to_check}'is specified but not in "
                "known_theme_packages or needs no separated install."
            )
    return theme_packages


def process_mkdocs_source_and_build(
    source_project_path: str,
    project_slug: str,
    version_identifier: str,
    base_output_dir: Path,
) -> Optional[str]:
    """Process a MKDOCS: Build project.

    Return the path to the dark or none HTML site in case of failure.
    """
    logger.info(f"--- Starting Mkdocs Build for{project_slug}v{version_identifier} ---")
    if not source_project_path:
        logger.error("Source Project Path Not Provided for Mkdocs Build.")
        return None
    project_root_p = Path(source_project_path)
    if not project_root_p.is_dir():
        logger.error(f"Source Project Path{project_root_p}Is Not a Valid Directory.")
        return None

    original_mkdocs_yml_path = _find_mkdocs_config_file(project_root_p)
    if not original_mkdocs_yml_path:
        logger.error(f"Could Not Find Mkdocs.yml in{project_root_p}. ABORTING.")
        return None
    original_config_content = _parse_mkdocs_config(original_mkdocs_yml_path)

    config_file_to_use_for_build = original_mkdocs_yml_path

    if original_config_content:
        processed_config_dict, config_was_modified = _preprocess_mkdocs_config(
            original_config_content
        )

        if config_was_modified and processed_config_dict is not None:
            processed_yml_filename = (
                f"{original_mkdocs_yml_path.stem}.devildex_processed.yml"
            )
            temp_processed_yml_path = (
                original_mkdocs_yml_path.parent / processed_yml_filename
            )
            try:
                with open(temp_processed_yml_path, "w", encoding="utf-8") as f_proc:
                    yaml.dump(
                        processed_config_dict,
                        f_proc,
                        sort_keys=False,
                        Dumper=yaml.Dumper,
                    )
                logger.info(
                    "Configurazione MkDocs preprocessata e salvata in: "
                    f"{temp_processed_yml_path}"
                )
                config_file_to_use_for_build = temp_processed_yml_path
            except Exception:
                logger.exception(
                    f"Errore nel salvare mkdocs.yml processato in "
                    f"{temp_processed_yml_path}"
                )
        else:
            logger.info(
                "Nessuna modifica di preprocessing necessaria per mkdocs.yml o "
                "il contenuto originale era None."
            )
    else:
        logger.warning("Contenuto di mkdocs.yml non parsato, skipping preprocessing.")

    final_html_output_dir = (
        base_output_dir / "mkdocs_builds" / project_slug / version_identifier
    ).resolve()
    try:
        if final_html_output_dir.exists():
            shutil.rmtree(final_html_output_dir)
        final_html_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.exception(
            f"Error Creating/Cleaning Mkdocs Output Directory{final_html_output_dir}"
        )
        return None

    build_successful = False
    try:
        with IsolatedVenvManager(
            project_name=f"mkdocs_{project_slug}-{version_identifier}"
        ) as venv:
            logger.info(f"Created Isolated Venv for Mkdocs at{venv.venv_path}")

            build_ctx = MkDocsBuildContext(
                config_content=original_config_content,
                project_root=project_root_p,
                original_yml_path=original_mkdocs_yml_path,
                processed_yml_path=config_file_to_use_for_build,
                final_output_dir=final_html_output_dir,
                project_slug=project_slug,
            )

            required_mkdocs_pkgs = _gather_mkdocs_required_packages(
                original_config_content
            )
            logger.info(
                "MkDocs related packages to install for "
                f"{project_slug}: {required_mkdocs_pkgs}"
            )

            dependencies_installed_ok = install_environment_dependencies(
                pip_executable=venv.pip_executable,
                project_name=f"mkdocs_{project_slug}",
                project_root_for_install=project_root_p,
                tool_specific_packages=required_mkdocs_pkgs,
                scan_for_project_requirements=True,
                install_project_editable=True,
            )
            if dependencies_installed_ok:
                build_successful = _perform_actual_mkdocs_build(
                    python_executable=venv.python_executable,
                    build_context=build_ctx,
                )
            else:
                logger.error(
                    f"Cannot proceed with MkDocs build for {project_slug} "
                    "due to failed dependency installation."
                )
                build_successful = False

    finally:
        logger.info(f"--- Finished Mkdocs Build for{project_slug} ---")
    return str(final_html_output_dir) if build_successful else None


def _perform_actual_mkdocs_build(
    python_executable: str, build_context: MkDocsBuildContext
) -> bool:
    """Execute the mkdocs build using the provided python executable and build context.

    Args:
        python_executable: Path to the python executable in the virtual environment.
        build_context: The MkDocsBuildContext containing configuration and paths.

    Returns:
        True if the build was successful, False otherwise.

    """
    pip_list_command = [python_executable, "-m", "pip", "list", "--format=json"]
    _, _, ret_code_pip_list = execute_command(
        pip_list_command,
        f"Pip list for {build_context.project_slug}",
    )
    config_file_for_command = build_context.processed_yml_path
    mkdocs_build_command = [
        python_executable,
        "-m",
        "mkdocs",
        "build",
        "--config-file",
        str(config_file_for_command.resolve()),
        "--site-dir",
        str(build_context.final_output_dir.resolve()),
    ]

    logger.info(f"Executing MkDocs build command: {' '.join(mkdocs_build_command)}")
    cwd_for_mkdocs = build_context.original_yml_path.parent

    stdout, stderr, return_code = execute_command(
        mkdocs_build_command,
        f"MkDocs build for {build_context.project_slug}",
        cwd=cwd_for_mkdocs,
    )

    if return_code == 0:
        logger.info(
            f"MkDocs build successful for {build_context.project_slug}. "
            f"Output: {build_context.final_output_dir}"
        )
        return True
    else:
        logger.error(
            f"MkDocs build for {build_context.project_slug} failed. RC: {return_code}"
        )
        logger.error(f"MkDocs build STDOUT:\n{stdout}")
        logger.error(f"MkDocs build STDERR:\n{stderr}")
        return False


def _extract_names_from_config_list_or_dict(
    config_data: Optional[Union[list[Union[str, dict[str, Any]]], dict[str, Any]]],
) -> list[str]:
    """Extract names from a configuration structure typical in mkdocs.yml."""
    names_to_check: list[str] = []
    if isinstance(config_data, list):
        for item in config_data:
            if isinstance(item, str):
                names_to_check.append(item)
            elif isinstance(item, dict) and item:
                name_candidate = next(iter(item.keys()))
                if "." in name_candidate and name_candidate.startswith("pymdownx"):
                    names_to_check.append(name_candidate)
                else:
                    names_to_check.append(name_candidate.split(".")[0])

    elif isinstance(config_data, dict):
        names_to_check.extend(list(config_data.keys()))
    return names_to_check


MkDocsPluginConfigItem = Union[str, dict[str, Any]]
MkDocsPluginConfigList = list[MkDocsPluginConfigItem]
MkDocsPluginConfigDict = dict[str, Any]

MkDocsPluginConfigType = Optional[
    Union[
        MkDocsPluginConfigList,
        MkDocsPluginConfigDict,
    ]
]


def _get_plugin_packages_to_install(
    plugins_config: Optional[list | dict],
    markdown_extensions_config: Optional[list | dict],
) -> list[str]:
    """Determine pip packages based on the configuration of plugins and extensions."""
    plugin_packages: list[str] = []

    all_names_to_check: list[str] = []
    all_names_to_check.extend(_extract_names_from_config_list_or_dict(plugins_config))
    all_names_to_check.extend(
        _extract_names_from_config_list_or_dict(markdown_extensions_config)
    )

    unique_names_to_check = sorted(list(set(all_names_to_check)))

    for name in unique_names_to_check:
        base_name_for_lookup = name.split(".")[0]

        package = KNOWN_PLUGIN_PACKAGES.get(name)
        if (
            package == BUILT_IN_MARKER
            or KNOWN_PLUGIN_PACKAGES.get(base_name_for_lookup) == BUILT_IN_MARKER
        ):
            continue
        if not package:
            package = KNOWN_PLUGIN_PACKAGES.get(base_name_for_lookup, name)
        if package:
            if package not in plugin_packages:
                plugin_packages.append(package)
                logger.debug(
                    f"Identified Plugin/Extension Package for " f"'{name}': {package}"
                )
        else:
            logger.debug(
                f"Plugin/Extension '{name}' (or base '{base_name_for_lookup}')"
                " is specified but not in KNOWN_PLUGIN_PACKAGES "
                "or needs no separate install."
            )
    return plugin_packages


def _gather_mkdocs_required_packages(mkdocs_config: Optional[dict]) -> list[str]:
    """Collect all the Python packages needed for a conf-based MKDOCS Builds."""
    packages_to_install: list[str] = ["mkdocs"]
    if mkdocs_config:
        packages_to_install.extend(
            _get_theme_packages_to_install(mkdocs_config.get("theme"))
        )
        packages_to_install.extend(
            _get_plugin_packages_to_install(
                mkdocs_config.get("plugins"),
                mkdocs_config.get("markdown_extensions"),
            )
        )

    unique_packages = sorted(list(set(pkg for pkg in packages_to_install if pkg)))

    return unique_packages
