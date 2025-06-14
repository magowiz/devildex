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


KNOWN_THEME_PACKAGES: dict[str, str] = {
    "material": "mkdocs-material",
}

KNOWN_PLUGIN_PACKAGES: dict[str, str] = {
    "mkdocstrings": "mkdocstrings[python]",
    "macros": "mkdocs-macros-plugin",
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
            config = yaml.safe_load(f)
        logger.info(f"Successfully Parsed Mkdocs Conference:{config_file_path}")
    except yaml.YAMLError:
        logger.exception(f"Error Parsing MKDOCS CONFERENCE FILE:{config_file_path}")
    except OSError:
        logger.exception(f"Error reading Mkdocs Config:{config_file_path}")
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


def _get_plugin_packages_to_install(
    plugins_config: Optional[Union[list[Union[str, dict[str, Any]]], dict[str, Any]]],
) -> list[str]:
    """Determine the pip packages based on the configuration of the plugins."""
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
            logger.debug(f"Identified Plugin Package for '{name}': {package}")
        else:
            logger.debug(
                f"Plugin '{name}'is specified but not in known_plugin_packages "
                "or needs no separate install."
            )
    return plugin_packages


def _install_mkdocs_dependencies_in_venv(
    pip_executable: str,
    mkdocs_config: Optional[dict],
    project_root_for_install: Optional[Path] = None,
) -> bool:
    """Install Mkdocs, theme, plugins and possibly the project itself."""
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
        logger.info(f"Attempt to Install Mkdocs Related Packages:{unique_packages}")
        pip_command_base = [pip_executable, "install", *unique_packages]
        _, _, return_code_base = execute_command(
            pip_command_base, "Install MkDocs and its dependencies"
        )
        if return_code_base != 0:
            logger.error("Failed to Install Mkdocs Related Packages.")
            return False
    else:
        logger.warning(
            "No Mkdocs Related Packages Identified for Installation "
            "(This is Unexpected)."
        )
    if project_root_for_install and project_root_for_install.exists():
        if (project_root_for_install / "setup.py").exists() or (
            project_root_for_install / "pyproject.toml"
        ).exists():
            logger.info(f"Attempt to Install Project from:{project_root_for_install}")
            pip_command_project = [
                pip_executable,
                "install",
                "-e",
                str(project_root_for_install),
            ]
            _, _, return_code_proj = execute_command(
                pip_command_project, f"Install Project{project_root_for_install.name}"
            )
            if return_code_proj != 0:
                logger.warning(
                    f"Failed to Install Project{project_root_for_install.name}, build "
                    "might be incomplete if project models are needed by plugins."
                )
        else:
            logger.debug(
                f"Project at{project_root_for_install}Does Not Sagan to Be Pip "
                "Installable (no setup.py/pyproject.toml). Skipping Project Install."
            )
    return True


def _execute_mkdocs_build_in_venv(
    venv: IsolatedVenvManager, ctx: MkDocsBuildContext
) -> bool:
    """Handle dependency installation, theming, and MkDocs build within the venv.

    Returns True if build is successful, False otherwise.
    """
    if not _install_mkdocs_dependencies_in_venv(
        venv.pip_executable, ctx.config_content, ctx.project_root
    ):
        logger.error("Failed to install dependencies in venv. Aborting MkDocs build.")
        return False

    path_to_use_for_mkdocs_yml = ctx.original_yml_path

    theme_manager = ThemeManager(
        project_path=ctx.original_yml_path.parent,
        doc_type="mkdocs",
        mkdocs_yml_file=ctx.original_yml_path,
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
            )
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
            build_successful = _execute_mkdocs_build_in_venv(venv, build_ctx)
    finally:
        logger.info(f"--- Finished Mkdocs Build for{project_slug} ---")
    return str(final_html_output_dir) if build_successful else None
