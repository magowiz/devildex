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
    "mkdocs-section-index": "mkdocs-section-index",
    "toc": None,
    "admonition": None,
    "codehilite": "Pygments",
    "footnotes": None,
    "attr_list": None,
    "md_in_html": None,
    "tables": None,
}


@dataclass
class MkDocsBuildContext:
    """Holds context for an MkDocs build operation."""

    config_content: Optional[dict]
    project_root: Path
    original_yml_path: Path
    final_output_dir: Path
    project_slug: str


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
        return config
    except yaml.YAMLError:
        logger.exception(
            f"Error parsing MkDocs Config file: {config_file_path}"
        )  # Log corretto
    except OSError:
        logger.exception(f"Error reading MkDocs Config file: {config_file_path}")
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
    mkdocs_config_content = _parse_mkdocs_config(original_mkdocs_yml_path)
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
                config_content=mkdocs_config_content,
                project_root=project_root_p,
                original_yml_path=original_mkdocs_yml_path,
                final_output_dir=final_html_output_dir,
                project_slug=project_slug,
            )
            required_mkdocs_pkgs = _gather_mkdocs_required_packages(
                mkdocs_config_content
            )
            # <LOG MIRATO 3 - INIZIO>
            logger.critical(
                f"MKDOCS_DEBUG_CHECKPOINT_3: Pacchetti richiesti (required_mkdocs_pkgs) prima di install_environment_dependencies: {required_mkdocs_pkgs}"
            )
            # <LOG MIRATO 3 - FINE>
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
    logger.critical(
        f"MKDOCS_BUILD_PIP_LIST_CHECKPOINT_2: Attempting to run pip list with command: {' '.join(pip_list_command)}"
    )
    stdout_pip_list, stderr_pip_list, ret_code_pip_list = execute_command(
        pip_list_command,
        f"Pip list for {build_context.project_slug}",
    )
    logger.critical(
        f"MKDOCS_BUILD_PIP_LIST_CHECKPOINT_3: Pip list ret_code: {ret_code_pip_list}"
    )
    logger.critical(
        f"MKDOCS_BUILD_PIP_LIST_CHECKPOINT_4: Pip list stdout:\n{stdout_pip_list}"
    )
    if stderr_pip_list:  # Logga stderr solo se non è vuoto
        logger.critical(
            f"MKDOCS_BUILD_PIP_LIST_CHECKPOINT_5: Pip list stderr:\n{stderr_pip_list}"
        )
    # <LOG MIRATO MKDOCS_BUILD - PROVA DEL NOVE CON PIP LIST - FINE>

    # <LOG MIRATO MKDOCS_BUILD - CHECK IMPORT CALLOUTS - INIZIO>
    logger.critical(
        f"MKDOCS_BUILD_IMPORT_CHECK_X1: Python executable for import check: {python_executable}"
    )
    check_import_command = [
        python_executable,
        "-c",
        "import sys; print(f'--- MKDOCS_BUILD sys.path START ---\\n{sys.path}\\n--- MKDOCS_BUILD sys.path END ---'); import callouts; print('--- MKDOCS_BUILD callouts module imported successfully ---')",
    ]
    logger.critical(
        f"MKDOCS_BUILD_IMPORT_CHECK_X2: Attempting to check importability of 'callouts' with command: {' '.join(check_import_command)}"
    )
    stdout_check, stderr_check, ret_code_check = execute_command(
        check_import_command,
        f"Check import callouts for {build_context.project_slug}",
    )
    logger.critical(
        f"MKDOCS_BUILD_IMPORT_CHECK_X3: Check import ret_code: {ret_code_check}"
    )
    logger.critical(
        f"MKDOCS_BUILD_IMPORT_CHECK_X4: Check import stdout:\n{stdout_check}"
    )
    if stderr_check:  # Logga stderr solo se non è vuoto
        logger.critical(
            f"MKDOCS_BUILD_IMPORT_CHECK_X5: Check import stderr:\n{stderr_check}"
        )
    # <LOG MIRATO MKDOCS_BUILD - CHECK IMPORT CALLOUTS - FINE>
    mkdocs_build_command = [
        python_executable,
        "-m",
        "mkdocs",
        "build",
        "--config-file",
        str(build_context.original_yml_path.resolve()),
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
        if not package:
            package = KNOWN_PLUGIN_PACKAGES.get(base_name_for_lookup)

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

    # In /home/magowiz/MEGA/projects/devildex/src/devildex/utils/venv_utils.py
    # ... (altri import e funzioni) ...


def _gather_mkdocs_required_packages(mkdocs_config: Optional[dict]) -> list[str]:
    """Raccoglie tutti i pacchetti Python necessari per una build MkDocs basata sulla configurazione."""
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
    # <LOG MIRATO 2 - INIZIO>
    logger.critical(
        f"MKDOCS_DEBUG_CHECKPOINT_2: Pacchetti unici raccolti da _gather_mkdocs_required_packages: {unique_packages}"
    )
    # <LOG MIRATO 2 - FINE>

    return unique_packages
