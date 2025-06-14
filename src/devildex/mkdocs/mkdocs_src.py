"""mkdocs build module."""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from devildex.utils.venv_cm import IsolatedVenvManager, VenvInitializationError
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
    version_identifier: str


def _extract_callouts_from_markdown_extensions(
    current_md_extensions: Optional[Union[list, dict]],
) -> tuple[Optional[Union[list, dict]], Any, bool]:
    """Extract 'callouts' from markdown_extensions if present.

    Args:
        current_md_extensions: The current markdown_extensions configuration.

    Returns:
        A tuple: (updated_md_extensions, extracted_callouts_value, was_modified).
        `updated_md_extensions` is a new list/dict if modified, otherwise the original.

    """
    if not current_md_extensions:
        return current_md_extensions, None, False

    callouts_value_extracted = None
    modified = False

    if isinstance(current_md_extensions, list):
        new_extensions_list = []
        for ext_item in current_md_extensions:
            if isinstance(ext_item, str) and ext_item == "callouts":
                callouts_value_extracted = "callouts"
                modified = True
            elif isinstance(ext_item, dict) and "callouts" in ext_item:
                callouts_value_extracted = ext_item.copy()
                modified = True
            else:
                new_extensions_list.append(ext_item)
        if modified:
            logger.info("Removed 'callouts' from 'markdown_extensions' (list).")
            return new_extensions_list, callouts_value_extracted, True
        return current_md_extensions, None, False

    if isinstance(current_md_extensions, dict) and "callouts" in current_md_extensions:
        updated_extensions_dict = current_md_extensions.copy()
        callouts_value_extracted = {"callouts": updated_extensions_dict.pop("callouts")}
        logger.info("Removed 'callouts' from 'markdown_extensions' (dict).")
        return updated_extensions_dict, callouts_value_extracted, True

    return current_md_extensions, None, False


def _is_plugin_callouts(plugin_item: Union[str, dict[str, Any]]) -> bool:
    """Check if a plugin item represents 'callouts'."""
    if isinstance(plugin_item, str) and plugin_item == "callouts":
        return True
    return isinstance(plugin_item, dict) and "callouts" in plugin_item


def _add_callouts_to_plugins_if_missing(
    current_plugins_config: Optional[Union[list, dict]],
    callouts_value_to_add: Union[str, dict[str, Any]],
) -> tuple[list, bool]:
    """Add the extracted 'callouts' value to the plugins list if not already present.

    Args:
        current_plugins_config: The current 'plugins' configuration.
        callouts_value_to_add: The 'callouts' configuration extracted
         from markdown_extensions.

    Returns:
        A tuple: (updated_plugins_list, was_added_boolean).

    """
    plugins_list: list = []
    # Ensure plugins_list is a list, creating a new one if necessary
    if isinstance(current_plugins_config, list):
        plugins_list = current_plugins_config.copy()  # Work on a copy
    elif current_plugins_config is not None:  # It's some other type
        logger.warning(
            f"'plugins' in mkdocs.yml was {type(current_plugins_config)}, not a list. "
            "Initializing as a new list for 'callouts' addition."
        )
        # plugins_list remains []
    # If current_plugins_config was None, plugins_list is already []

    is_already_plugin = any(_is_plugin_callouts(p_item) for p_item in plugins_list)

    if not is_already_plugin:
        plugins_list.append(callouts_value_to_add)
        logger.info(f"Added '{callouts_value_to_add}' to 'plugins'.")
        return plugins_list, True

    return plugins_list, False


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

    processed_config = original_config_content.copy()  # Shallow copy
    overall_config_modified = False

    current_md_extensions = processed_config.get("markdown_extensions")
    updated_md_extensions, callouts_value_extracted, ext_was_modified = (
        _extract_callouts_from_markdown_extensions(current_md_extensions)
    )

    if ext_was_modified:
        processed_config["markdown_extensions"] = updated_md_extensions
        overall_config_modified = True

        if callouts_value_extracted is not None:
            current_plugins = processed_config.get("plugins")
            updated_plugins_list, plugin_list_was_modified = (
                _add_callouts_to_plugins_if_missing(
                    current_plugins, callouts_value_extracted
                )
            )

            if plugin_list_was_modified:
                processed_config["plugins"] = updated_plugins_list
                # overall_config_modified is already True

    return processed_config, overall_config_modified


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


# Helper 1: Initial validation and config loading
def _validate_paths_and_load_config(
    source_project_path_str: str,
) -> tuple[Optional[Path], Optional[Path], Optional[dict]]:
    """Validate input paths and load the MkDocs configuration."""
    if not source_project_path_str:
        logger.error("Source Project Path Not Provided for Mkdocs Build.")
        return None, None, None
    project_root_p = Path(source_project_path_str)
    if not project_root_p.is_dir():
        logger.error(f"Source Project Path {project_root_p} Is Not a Valid Directory.")
        return None, None, None

    original_mkdocs_yml_path = _find_mkdocs_config_file(project_root_p)
    if not original_mkdocs_yml_path:
        logger.error(f"Could Not Find Mkdocs.yml in {project_root_p}. ABORTING.")
        return None, None, None

    original_config_content = _parse_mkdocs_config(original_mkdocs_yml_path)
    return project_root_p, original_mkdocs_yml_path, original_config_content


def _prepare_config_for_build(
    original_config_content: Optional[dict], original_mkdocs_yml_path: Path
) -> Path:
    """Preprocesses MkDocs config and returns the path to the config file to use."""
    config_file_to_use_for_build = original_mkdocs_yml_path

    if not original_config_content:
        logger.warning(
            "MkDocs config content not parsed or absent, skipping preprocessing."
            " Using original path: %s",
            original_mkdocs_yml_path,
        )
        return original_mkdocs_yml_path

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
                "Preprocessed MkDocs configuration saved to: %s",
                temp_processed_yml_path,
            )
            config_file_to_use_for_build = temp_processed_yml_path
        except (OSError, yaml.YAMLError):
            logger.exception(
                "Error saving processed mkdocs.yml to %s. Using original path: %s",
                temp_processed_yml_path,
                original_mkdocs_yml_path,
            )
            config_file_to_use_for_build = original_mkdocs_yml_path
    else:
        logger.info(
            "No preprocessing modifications needed for mkdocs.yml or "
            "original content was None. Using original path: %s",
            original_mkdocs_yml_path,
        )
    return config_file_to_use_for_build


def _prepare_mkdocs_output_directory(
    base_output_dir: Path, project_slug: str, version_identifier: str
) -> Optional[Path]:
    """Create or cleans the final output directory for the MkDocs build."""
    final_html_output_dir = (
        base_output_dir / "mkdocs_builds" / project_slug / version_identifier
    ).resolve()
    try:
        if final_html_output_dir.exists():
            shutil.rmtree(final_html_output_dir)
        final_html_output_dir.mkdir(parents=True, exist_ok=True)

    except OSError:
        logger.exception(
            "Error Creating/Cleaning Mkdocs Output Directory %s", final_html_output_dir
        )
        return None
    else:
        return final_html_output_dir


def _execute_mkdocs_build_in_venv(build_context: MkDocsBuildContext) -> bool:
    """Manage venv creation, dependency installation, and executes the MkDocs build."""
    build_successful = False
    try:
        with IsolatedVenvManager(
            project_name=f"mkdocs_{build_context.project_slug}-{build_context.version_identifier}"
        ) as venv:
            logger.info("Created Isolated Venv for Mkdocs at %s", venv.venv_path)

            required_mkdocs_pkgs = _gather_mkdocs_required_packages(
                build_context.config_content
            )
            logger.info(
                "MkDocs related packages to install for %s: %s",
                build_context.project_slug,
                required_mkdocs_pkgs,
            )

            dependencies_installed_ok = install_environment_dependencies(
                pip_executable=venv.pip_executable,
                project_name=f"mkdocs_{build_context.project_slug}",
                project_root_for_install=build_context.project_root,
                tool_specific_packages=required_mkdocs_pkgs,
                scan_for_project_requirements=True,
                install_project_editable=True,
            )
            if dependencies_installed_ok:
                build_successful = _perform_actual_mkdocs_build(
                    python_executable=venv.python_executable,
                    build_context=build_context,
                )
            else:
                logger.error(
                    "Cannot proceed with MkDocs build for %s due to "
                    "failed dependency installation.",
                    build_context.project_slug,
                )
    except VenvInitializationError:
        logger.exception(
            "Failed to initialize virtual environment for MkDocs build for %s.",
            build_context.project_slug,
        )
        build_successful = False
    except OSError:
        logger.exception(
            "Unexpected error during isolated MkDocs build for %s.",
            build_context.project_slug,
        )
        build_successful = False

    return build_successful


def process_mkdocs_source_and_build(
    source_project_path: str,
    project_slug: str,
    version_identifier: str,
    base_output_dir: Path,
) -> Optional[str]:
    """Process an MkDocs project: find config, preprocess, install deps, and build."""
    logger.info(
        f"--- Starting Mkdocs Build for {project_slug} v{version_identifier} ---"
    )
    final_result_path: Optional[str] = None

    try:
        project_root_p, original_mkdocs_yml_path, original_config_content = (
            _validate_paths_and_load_config(source_project_path)
        )

        if not project_root_p or not original_mkdocs_yml_path:
            return None
        config_file_to_use_for_build = _prepare_config_for_build(
            original_config_content, original_mkdocs_yml_path
        )

        final_html_output_dir = _prepare_mkdocs_output_directory(
            base_output_dir, project_slug, version_identifier
        )
        if not final_html_output_dir:
            return None
        build_ctx = MkDocsBuildContext(
            config_content=original_config_content,
            project_root=project_root_p,
            original_yml_path=original_mkdocs_yml_path,
            final_output_dir=final_html_output_dir,
            project_slug=project_slug,
            processed_yml_path=config_file_to_use_for_build,
            version_identifier=version_identifier,
        )
        build_successful = _execute_mkdocs_build_in_venv(build_ctx)

        if build_successful:
            final_result_path = str(final_html_output_dir)

    except (OSError, RuntimeError):
        logger.exception(
            f"Unexpected critical error during MkDocs processing for {project_slug}"
        )
        final_result_path = None
    finally:
        status_message = (
            "successfully" if final_result_path else "with errors or aborted"
        )
        logger.info(
            f"--- Finished Mkdocs Build for {project_slug} {status_message} ---"
        )

    return final_result_path


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
