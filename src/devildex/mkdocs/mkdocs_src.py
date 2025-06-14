"""mkdocs build module."""

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from devildex.theming.manager import ThemeManager
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import execute_command

logger = logging.getLogger(__name__)
MKDOCS_CONFIG_FILE = "mkdocs.yml"

# Mappature per pacchetti noti di temi e plugin
# Questo semplifica l'aggiunta di nuovi temi/plugin in futuro
KNOWN_THEME_PACKAGES: dict[str, str] = {
    "material": "mkdocs-material",
    # Aggiungi qui altri temi noti e i loro pacchetti pip
    # Esempio: "readthedocs": "mkdocs-readthedocs-theme", (se non built-in)
}

KNOWN_PLUGIN_PACKAGES: dict[str, str] = {
    "mkdocstrings": "mkdocstrings[python]",
    "macros": "mkdocs-macros-plugin",
}


# <<< NEW DATACLASS >>>
@dataclass
class MkDocsBuildContext:
    """Holds context for an MkDocs build operation."""

    config_content: Optional[dict]
    project_root: Path
    original_yml_path: Path
    final_output_dir: Path
    project_slug: str


def _find_mkdocs_config_file(project_root_path: Path) -> Optional[Path]:
    """Trova il file mkdocs.yml, tipicamente alla root del progetto."""
    mkdocs_conf = project_root_path / MKDOCS_CONFIG_FILE
    if mkdocs_conf.is_file():
        logger.info(f"Found MkDocs config file: {mkdocs_conf}")
        return mkdocs_conf
    logger.warning(
        f"MkDocs config file not found at {mkdocs_conf}."
        " Searching in 'docs' subdir..."
    )
    mkdocs_conf_in_docs = project_root_path / "docs" / MKDOCS_CONFIG_FILE
    if mkdocs_conf_in_docs.is_file():
        logger.info(f"Found MkDocs config file in docs/ subdir: {mkdocs_conf_in_docs}")
        return mkdocs_conf_in_docs
    logger.error(
        f"MkDocs config file not found in {project_root_path} " "or its 'docs' subdir."
    )
    return None


def _parse_mkdocs_config(config_file_path: Path) -> Optional[dict]:
    """Esegue il parsing del file mkdocs.yml."""
    try:
        with open(config_file_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.info(f"Successfully parsed MkDocs config: {config_file_path}")
    except yaml.YAMLError:
        logger.exception(f"Error parsing MkDocs config file: {config_file_path}")
    except OSError:
        logger.exception(f"Error reading MkDocs config file: {config_file_path}")
    else:
        return config
    return None


def _get_theme_packages_to_install(
    theme_config: Optional[Union[str, dict[str, Any]]],
) -> list[str]:
    """Determina i pacchetti pip necessari in base alla configurazione del tema."""
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
                f"Identified theme package for '{theme_name_to_check}': {package}"
            )
        else:
            logger.debug(
                f"Theme '{theme_name_to_check}' is specified but not"
                " in KNOWN_THEME_PACKAGES or needs no separate install."
            )
    return theme_packages


def _get_plugin_packages_to_install(
    plugins_config: Optional[Union[list[Union[str, dict[str, Any]]], dict[str, Any]]],
) -> list[str]:
    """Determina i pacchetti pip necessari in base alla configurazione dei plugin."""
    plugin_packages: list[str] = []
    plugin_names_to_check: list[str] = []

    if isinstance(plugins_config, list):
        for plugin_item in plugins_config:
            if isinstance(plugin_item, str):
                plugin_names_to_check.append(plugin_item)
            elif isinstance(plugin_item, dict) and plugin_item:
                plugin_names_to_check.append(next(iter(plugin_item.keys())))
    elif isinstance(plugins_config, dict):
        plugin_names_to_check.extend(list(plugins_config.keys()))

    for name in plugin_names_to_check:
        package = KNOWN_PLUGIN_PACKAGES.get(name)
        if package:
            plugin_packages.append(package)
            logger.debug(f"Identified plugin package for '{name}': {package}")
        else:
            logger.debug(
                f"Plugin '{name}' is specified but not in KNOWN_PLUGIN_PACKAGES"
                " or needs no separate install."
            )
    return plugin_packages


def _install_mkdocs_dependencies_in_venv(
    pip_executable: str,
    mkdocs_config: Optional[dict],
    project_root_for_install: Optional[Path] = None,
) -> bool:
    """Installa MkDocs, tema, plugin ed eventualmente il progetto stesso."""
    packages_to_install: list[str] = ["mkdocs"]

    if mkdocs_config:
        packages_to_install.extend(
            _get_theme_packages_to_install(mkdocs_config.get("theme"))
        )
        packages_to_install.extend(
            _get_plugin_packages_to_install(mkdocs_config.get("plugins"))
        )

    unique_packages = list(set(packages_to_install))
    if unique_packages:
        logger.info(f"Attempting to install MkDocs related packages: {unique_packages}")
        pip_command_base = [pip_executable, "install", *unique_packages]
        _, _, return_code_base = execute_command(
            pip_command_base, "Install MkDocs and its dependencies"
        )
        if return_code_base != 0:
            logger.error("Failed to install MkDocs related packages.")
            return False
    else:
        logger.warning(
            "No MkDocs related packages identified for "
            "installation (this is unexpected)."
        )

    if project_root_for_install and project_root_for_install.exists():
        if (project_root_for_install / "setup.py").exists() or (
            project_root_for_install / "pyproject.toml"
        ).exists():
            logger.info(
                f"Attempting to install project from: {project_root_for_install}"
            )
            pip_command_project = [
                pip_executable,
                "install",
                "-e",
                str(project_root_for_install),
            ]
            _, _, return_code_proj = execute_command(
                pip_command_project, f"Install project {project_root_for_install.name}"
            )
            if return_code_proj != 0:
                logger.warning(
                    f"Failed to install project {project_root_for_install.name}, "
                    "build might be incomplete if project modules"
                    " are needed by plugins."
                )
        else:
            logger.debug(
                f"Project at {project_root_for_install} does not appear"
                " to be pip installable (no setup.py/pyproject.toml)."
                " Skipping project install."
            )
    return True


def _execute_mkdocs_build_in_venv(  # <<< MODIFIED SIGNATURE
    venv: IsolatedVenvManager, ctx: MkDocsBuildContext  # <<< USING DATACLASS
) -> bool:
    """Handle dependency installation, theming, and MkDocs build within the venv.

    Returns True if build is successful, False otherwise.
    """
    if not _install_mkdocs_dependencies_in_venv(
        venv.pip_executable, ctx.config_content, ctx.project_root  # <<< USING ctx
    ):
        logger.error("Failed to install dependencies in venv. Aborting MkDocs build.")
        return False

    path_to_use_for_mkdocs_yml = ctx.original_yml_path  # Default

    theme_manager = ThemeManager(
        project_path=ctx.original_yml_path.parent,  # <<< USING ctx
        doc_type="mkdocs",
        mkdocs_yml_file=ctx.original_yml_path,  # <<< USING ctx
    )

    with tempfile.TemporaryDirectory(
        prefix="devildex_mkdocs_theme_"
    ) as temp_theme_dir_str:
        temp_theme_dir_path = Path(temp_theme_dir_str)
        logger.debug(
            f"Created temporary directory for themed YAML: {temp_theme_dir_path}"
        )

        if hasattr(theme_manager, "mkdocs_apply_customizations"):
            custom_yml_path = theme_manager.mkdocs_apply_customizations(
                temp_theme_dir_path
            )  # <<< PASS THE PATH
            if custom_yml_path and custom_yml_path.exists():
                path_to_use_for_mkdocs_yml = custom_yml_path
                logger.info(f"Using themed mkdocs.yml: {path_to_use_for_mkdocs_yml}")
            else:
                logger.warning(
                    "Theming did not produce a new mkdocs.yml or path was invalid, "
                    "using original."
                )
        else:
            logger.warning(
                "ThemeManager does not have 'mkdocs_apply_customizations'"
                " method yet. Using original mkdocs.yml."
            )

        build_cwd = path_to_use_for_mkdocs_yml.parent

        mkdocs_command = [
            venv.python_executable,
            "-m",
            "mkdocs",
            "build",
            "--config-file",
            str(path_to_use_for_mkdocs_yml.resolve()),
            "--site-dir",
            str(ctx.final_output_dir.resolve()),
            "--clean",
        ]
        logger.info(
            "Executing MkDocs: " f"{' '.join(mkdocs_command)} in CWD: {build_cwd}"
        )
        stdout, stderr, return_code = execute_command(
            mkdocs_command,
            f"MkDocs build for {ctx.project_slug}",
            cwd=build_cwd,
        )

        if return_code == 0:
            logger.info(f"MkDocs build for {ctx.project_slug} completed successfully.")
            return True

        logger.error(
            f"MkDocs build for {ctx.project_slug}" f" failed. RC: {return_code}"
        )
        logger.error(f"MkDocs stdout:\n{stdout}")
        logger.error(f"MkDocs stderr:\n{stderr}")
        return False


def process_mkdocs_source_and_build(
    source_project_path: str,
    project_slug: str,
    version_identifier: str,
    base_output_dir: Path,
) -> Optional[str]:
    """Process un progetto MkDocs: build.

    Restituisce il path al sito HTML buildato o None in caso di fallimento.
    """
    logger.info(
        f"\n--- Starting MkDocs Build for {project_slug} v{version_identifier} ---"
    )
    if not source_project_path:
        logger.error("Source project path not provided for MkDocs build.")
        return None

    project_root_p = Path(source_project_path)
    if not project_root_p.is_dir():
        logger.error(f"Source project path {project_root_p} is not a valid directory.")
        return None

    original_mkdocs_yml_path = _find_mkdocs_config_file(project_root_p)
    if not original_mkdocs_yml_path:
        logger.error(f"Could not find mkdocs.yml in {project_root_p}. Aborting.")
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
            "Error creating/cleaning MkDocs output "
            f"directory {final_html_output_dir}"
        )
        return None

    build_successful = False
    try:
        with IsolatedVenvManager(
            project_name=f"mkdocs_{project_slug}-{version_identifier}"
        ) as venv:
            logger.info(f"Created isolated venv for MkDocs at {venv.venv_path}")

            # <<< CREATE AND PASS CONTEXT OBJECT >>>
            build_ctx = MkDocsBuildContext(
                config_content=mkdocs_config_content,
                project_root=project_root_p,
                original_yml_path=original_mkdocs_yml_path,
                final_output_dir=final_html_output_dir,
                project_slug=project_slug,
            )
            build_successful = _execute_mkdocs_build_in_venv(venv, build_ctx)

    except Exception:
        logger.exception(
            "Critical error during MkDocs isolated " f"build for {project_slug}"
        )
    finally:
        logger.info(f"--- Finished MkDocs Build for {project_slug} ---")

    return str(final_html_output_dir) if build_successful else None
