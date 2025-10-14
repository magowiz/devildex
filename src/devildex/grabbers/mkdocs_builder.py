import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union, Any
import yaml

from devildex.grabbers.abstract_grabber import AbstractGrabber
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command,
    install_project_and_dependencies_in_venv,
)
# from devildex.scanner.scanner import is_mkdocs_project # To be implemented

if TYPE_CHECKING:
    from devildex.orchestrator.build_context import BuildContext

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s"
    )

MKDOCS_CONFIG_FILE = "mkdocs.yml"
REQUIREMENTS_FILENAME = "requirements.txt"

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
    "mdx_gh_links": "mdx-gh-links",
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
        logger.exception(f"Error parsing MkDocs Config file: {config_file_path}")
    except OSError:
        logger.exception(f"Error reading MkDocs Config file: {config_file_path}")
    else:
        return config
    return None


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
                if "." in name_candidate:
                    names_to_check.append(name_candidate)
                else:
                    names_to_check.append(name_candidate.split(".")[0])

    elif isinstance(config_data, dict):
        names_to_check.extend(list(config_data.keys()))
    return names_to_check


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

    unique_names_to_check = sorted(set(all_names_to_check))

    for name in unique_names_to_check:
        package_to_install: Optional[str] = None

        # Check for exact match first
        if name in KNOWN_PLUGIN_PACKAGES:
            package_to_install = KNOWN_PLUGIN_PACKAGES[name]
        else:
            # Check for base name if no exact match
            base_name_for_lookup = name.split(".")[0]
            if base_name_for_lookup in KNOWN_PLUGIN_PACKAGES:
                package_to_install = KNOWN_PLUGIN_PACKAGES[base_name_for_lookup]

        if package_to_install and package_to_install != BUILT_IN_MARKER:
            if package_to_install not in plugin_packages:
                plugin_packages.append(package_to_install)
                logger.debug(
                    f"Identified Plugin/Extension Package for '{name}': {package_to_install}"
                )
        elif package_to_install == BUILT_IN_MARKER:
            logger.debug(f"Plugin/Extension '{name}' is a built-in feature. No installation needed.")
        else:
            logger.debug(
                f"Plugin/Extension '{name}' is specified but not in KNOWN_PLUGIN_PACKAGES "
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
        # Handle 'callouts' markdown extension which is provided by a plugin
        plugins_config = mkdocs_config.get("plugins", [])
        markdown_extensions_config = mkdocs_config.get("markdown_extensions", [])

        if "callouts" in _extract_names_from_config_list_or_dict(markdown_extensions_config):
            if isinstance(plugins_config, list):
                plugins_config.append("mkdocs-callouts")
            elif isinstance(plugins_config, dict):
                plugins_config["mkdocs-callouts"] = {} # Add as an empty dict if it's a dict

        packages_to_install.extend(
            _get_plugin_packages_to_install(
                plugins_config,
                markdown_extensions_config,
            )
        )
        plugin_names = _extract_names_from_config_list_or_dict(
            mkdocs_config.get("plugins")
        )
        if "mkdocstrings" in plugin_names:
            logger.info(
                "mkdocstrings plugin detected. Adding 'ruff' for code formatting."
            )
            packages_to_install.append("ruff")
    unique_packages = sorted(set(pkg for pkg in packages_to_install if pkg))

    return unique_packages

def _find_mkdocs_doc_requirements_file(
    source_dir_path: Path,
    clone_root_path: Path,
    project_slug: str
) -> Path | None:
    """Find the specific requirements file for MkDocs documentation."""
    candidate_req_paths = [
        source_dir_path / REQUIREMENTS_FILENAME,
        source_dir_path.parent / REQUIREMENTS_FILENAME,
        clone_root_path / "doc-requirements.txt",
        clone_root_path / "docs-requirements.txt",
        clone_root_path / "dev-requirements.txt",
        clone_root_path / "requirements-doc.txt",
        clone_root_path / "requirements-docs.txt",
        clone_root_path / "requirements-dev.txt",
        clone_root_path / REQUIREMENTS_FILENAME,
        clone_root_path / "docs" / REQUIREMENTS_FILENAME,
        clone_root_path / "doc" / REQUIREMENTS_FILENAME,
        clone_root_path / "requirements" / "docs.txt",
        clone_root_path / "requirements" / "doc.txt",
    ]
    for req_path_candidate in candidate_req_paths:
        if req_path_candidate.exists():
            logger.info("Found documentation requirements file: %s", req_path_candidate)
            return req_path_candidate
    logger.info(
        "No specific 'requirements.txt' found for documentation in common "
        "locations for %s.",
        project_slug,
    )
    return None


class MkDocsBuilder(AbstractGrabber):
    def generate_docset(self, source_path: Path, output_path: Path, context: "BuildContext") -> bool:
        logger.info(
            "\n--- Starting Isolated MkDocs Build for %s v%s ---",
            context.project_slug,
            context.version_identifier,
        )

        mkdocs_config_file_path = _find_mkdocs_config_file(source_path)
        if not mkdocs_config_file_path:
            logger.error(
                "Critical Error: mkdocs.yml not found in %s or its 'docs' subdir.", source_path
            )
            return False

        mkdocs_config_content = _parse_mkdocs_config(mkdocs_config_file_path)
        if mkdocs_config_content is None:
            logger.error("Failed to parse mkdocs.yml at %s. Aborting build.", mkdocs_config_file_path)
            return False

        # Ensure docs_dir is explicitly set to an absolute path
        docs_dir_path = source_path / "docs"
        if not docs_dir_path.is_dir():
            logger.error("MkDocs 'docs' directory not found at %s. Aborting build.", docs_dir_path)
            return False
        mkdocs_config_content["docs_dir"] = str(docs_dir_path.resolve())
        logger.info("Explicitly set 'docs_dir' to absolute path: %s in MkDocs config.", mkdocs_config_content["docs_dir"])

        # Ensure hooks path is absolute if specified
        if "hooks" in mkdocs_config_content and mkdocs_config_content["hooks"]:
            hooks_path = Path(mkdocs_config_content["hooks"])
            if not hooks_path.is_absolute():
                absolute_hooks_path = source_path / hooks_path
                if not absolute_hooks_path.is_file():
                    logger.error("MkDocs 'hooks' file not found at %s. Aborting build.", absolute_hooks_path)
                    return False
                mkdocs_config_content["hooks"] = str(absolute_hooks_path.resolve())
                logger.info("Explicitly set 'hooks' to absolute path: %s in MkDocs config.", mkdocs_config_content["hooks"])

        # Special handling for 'callouts' markdown extension, which is provided by a plugin
        if "markdown_extensions" in mkdocs_config_content:
            markdown_extensions = mkdocs_config_content["markdown_extensions"]
            if isinstance(markdown_extensions, list):
                if "callouts" in markdown_extensions:
                    markdown_extensions.remove("callouts")
                    logger.info("Removed 'callouts' from markdown_extensions.")

                    if "plugins" not in mkdocs_config_content:
                        mkdocs_config_content["plugins"] = []
                    
                    # Ensure 'callouts' is added as a plugin, not 'mkdocs-callouts'
                    if isinstance(mkdocs_config_content["plugins"], list):
                        if "callouts" not in mkdocs_config_content["plugins"]:
                            mkdocs_config_content["plugins"].append("callouts")
                    elif isinstance(mkdocs_config_content["plugins"], dict):
                        if "callouts" not in mkdocs_config_content["plugins"]:
                            mkdocs_config_content["plugins"]["callouts"] = {}
                    logger.info("Added 'callouts' to plugins section.")

        # Ensure docs_dir is explicitly set relative to source_path
        if "docs_dir" not in mkdocs_config_content:
            mkdocs_config_content["docs_dir"] = "docs"
            logger.info("Explicitly set 'docs_dir' to 'docs' in MkDocs config.")

        final_output_dir = (
            Path(output_path) / context.project_slug / context.version_identifier
        ).resolve()

        logger.info("MkDocs HTML output directory: %s", final_output_dir)

        try:
            if final_output_dir.exists():
                logger.info(
                    "Removing existing output directory: %s",
                    final_output_dir,
                )
                shutil.rmtree(final_output_dir)
            final_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception(
                "Error creating/cleaning output directory %s",
                final_output_dir,
            )
            return False

        try:
            with IsolatedVenvManager(
                project_name=f"{context.project_slug}-{context.version_identifier}"
            ) as venv:
                required_mkdocs_pkgs = _gather_mkdocs_required_packages(mkdocs_config_content)
                logger.info(
                    "MkDocs related packages to install for %s: %s",
                    context.project_slug,
                    required_mkdocs_pkgs,
                )

                install_success = install_project_and_dependencies_in_venv(
                    pip_executable=venv.pip_executable,
                    project_name=context.project_slug,
                    project_root_for_install=context.project_root_for_install,
                    doc_requirements_path=_find_mkdocs_doc_requirements_file(
                        source_path, context.project_root_for_install, context.project_slug
                    ),
                    base_packages_to_install=required_mkdocs_pkgs,
                )
                if not install_success:
                    logger.error(
                        "CRITICAL: Installation of project/dependencies (including MkDocs) "
                        "for %s FAILED or had critical issues. Aborting MkDocs build.",
                        context.project_slug,
                    )
                    return False

                # Create a temporary mkdocs.yml with the modified content
                with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=".yml") as temp_config_file:
                    yaml.dump(mkdocs_config_content, temp_config_file)
                temp_config_file_path = Path(temp_config_file.name)
                logger.info("Created temporary MkDocs config file: %s", temp_config_file_path)

                mkdocs_command_list = [
                    str(venv.python_executable), # Ensure it's a string
                    "-m",
                    "mkdocs",
                    "build",
                    "--config-file",
                    str(temp_config_file_path), # Use the temporary config file
                    "--site-dir",
                    str(final_output_dir),
                ]

                logger.info("Executing MkDocs: %s", " ".join(mkdocs_command_list))
                try:
                    stdout, stderr, return_code = execute_command(
                        mkdocs_command_list,
                        f"MkDocs build for {context.project_slug}",
                        cwd=source_path,
                    )
                finally:
                    if temp_config_file_path.exists():
                        temp_config_file_path.unlink()
                        logger.info("Cleaned up temporary MkDocs config file: %s", temp_config_file_path)

                if return_code == 0:
                    logger.info(
                        "MkDocs build for %s completed successfully.",
                        context.project_slug,
                    )
                    return True
                else:
                    logger.error(
                        "MkDocs build for %s failed. Return code: %s",
                        context.project_slug,
                        return_code,
                    )
                    logger.error("MkDocs stdout:\n%s", stdout)
                    logger.error("MkDocs stderr:\n%s", stderr)
                    return False

        except RuntimeError:
            logger.exception(
                "Critical error during isolated build setup for %s",
                context.project_slug,
            )
            return False
        except OSError:
            logger.exception(
                "Error during MkDocs build for %s",
                context.project_slug,
            )
            return False
        finally:
            logger.info(
                "--- Finished Isolated MkDocs Build for %s ---",
                context.project_slug,
            )

    def can_handle(self, source_path: Path, context: "BuildContext") -> bool:
        # Check for mkdocs.yml in the source_path
        return (source_path / MKDOCS_CONFIG_FILE).exists()


