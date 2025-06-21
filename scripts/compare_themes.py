"""script to compare themes."""

import argparse
import logging
import shutil
import subprocess
import tempfile
import webbrowser
from argparse import Namespace
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from dev_themes_server import start_server

from devildex.docstrings.docstrings_src import DocStringsSrc
from devildex.info import PROJECT_ROOT as DEVILDEX_PROJECT_ROOT
from devildex.mkdocs.mkdocs_src import (
    process_mkdocs_source_and_build,
)
from devildex.readthedocs.readthedocs_src import (
    CONF_SPHINX_FILE,
)
from devildex.theming.manager import ThemeManager
from devildex.utils.venv_cm import IsolatedVenvManager, VenvInitializationError
from devildex.utils.venv_utils import (
    InstallConfig,
    execute_command,
    install_environment_dependencies,
)

SERVER_PORT = 8001
SPHINX_COMMON_PACKAGES = [
    "sphinx",
    "pallets-sphinx-themes",
    "sphinxcontrib.log-cabinet",
    "sphinx-tabs",
]

SUPPORTED_TYPES = ["sphinx", "pdoc3", "mkdocs"]
KNOWN_PROJECTS = {
    "black": {
        "repo_url": "https://github.com/psf/black.git",
        "doc_type": "sphinx",
        "doc_source_path_relative": "docs/",
        "default_branch": "main",
    },
    "flask": {
        "repo_url": "https://github.com/pallets/flask.git",
        "doc_type": "sphinx",
        "doc_source_path_relative": "docs/",
        "default_branch": "main",
    },
    "fastapi": {
        "repo_url": "https://github.com/tiangolo/fastapi.git",
        "doc_type": "pdoc3",
        "module_name": "fastapi",
        "default_branch": "master",
    },
    "mkdocs": {
        "repo_url": "https://github.com/mkdocs/mkdocs.git",
        "doc_type": "mkdocs",
        "default_branch": "master",
    },
}
FIXED_BUILD_OUTPUT_DIR = DEVILDEX_PROJECT_ROOT / "build" / "devildex_docs"

PDOC3_DEVILDEX_THEME_PATH = (
    DEVILDEX_PROJECT_ROOT / "src" / "devildex" / "theming" / "devildex_pdoc3_theme"
)

logger = logging.getLogger("theme_comparator")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class BuildContext:
    """Encapsulates all state and configuration for a single build process.

    This dataclass acts as a central container for all the necessary paths,
    configurations, and command-line arguments required to perform a build.
    It is created by `setup_environment` and passed through the various
    build functions to avoid long argument lists and to maintain a clear
    state.

    Attributes:
        project_config: The configuration dictionary for the target project
            from `KNOWN_PROJECTS`.
        args: The parsed command-line arguments from `argparse`.
        cloned_repo_path: The path to the temporary directory where the
            source repository has been cloned.
        build_outputs_base_dir: The base directory where the final HTML
            documentation will be placed.
        run_temp_dir: The root temporary directory for the entire script
            execution, containing the clone and build outputs.
        branch_to_clone: The name of the git branch that was cloned.
        build_id: An optional unique identifier for the build, primarily
            used in server mode to signal a refresh.

    """

    project_config: dict
    args: Namespace
    cloned_repo_path: Path
    build_outputs_base_dir: Path
    run_temp_dir: Path
    branch_to_clone: str
    build_id: str | None = None


class ServerRebuilder:
    """Encapsulates the state and logic required for server-driven rebuilds.

    This class acts as a container (or "backpack") that carries the necessary
    `BuildContext` and other relevant information, allowing the server's
    rebuild callback to access the context needed to perform a new build
    without requiring additional arguments.
    """

    def __init__(self, base_context: BuildContext) -> None:
        """Initialize the ServerRebuilder instance.

        Args:
            base_context: The initial BuildContext containing all the necessary
                configuration and paths for a build. This context will be used
                as a template for subsequent rebuilds triggered by the server.

        """
        self.base_context = base_context

    def rebuild(self) -> None:
        """Rebuilds the documentation when triggered by the development server.

        This method acts as a callback for the live-reload server. It uses the
        `base_context` stored in the instance to perform a new 'devil' build,
        then updates a signal file that the browser polls to trigger a refresh.
        """
        logger.info("\n--- Starting browser-requested rebuild ---")

        rebuild_ctx = replace(
            self.base_context,
            build_id=datetime.now().strftime("%H:%M:%S"),
        )

        _, devil_entry_point = _perform_builds(ctx=rebuild_ctx)

        if devil_entry_point:
            signal_file = devil_entry_point.parent / "_build_signal.txt"
            signal_file.write_text(rebuild_ctx.build_id)
            logger.info(f"signal File updated: {signal_file}")
        logger.info("--- Rebuild completed ---")


def clone_repository(repo_url: str, target_dir: Path, branch: str) -> bool:
    """Clones a Git repository into a target directory.

    It handles the cleanup of an existing target directory and includes fallback
    logic to the 'main' branch if the specified branch is not found.

    Args:
        repo_url: The URL of the Git repository to clone.
        target_dir: The local path where the repository will be cloned.
        branch: The specific branch to clone.

    Returns:
        True if the clone was successful, False otherwise.

    """
    if target_dir.exists():
        logger.info(f"Cleaning up existing clone directory: {target_dir}")
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    git_executable = shutil.which("git")
    if not git_executable:
        logger.error("Git not found. Please ensure it is installed and in your PATH.")
        return False

    cmd = [git_executable, "clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([repo_url, str(target_dir)])

    logger.info(
        f"Attempting to clone {repo_url} (branch: {branch or 'default'}) "
        f"into {target_dir}..."
    )
    process = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, check=False, encoding="utf-8"
    )

    if process.returncode == 0:
        logger.info("Clone successful.")
        return True
    else:
        logger.error(
            f"Clone failed. Branch: {branch or 'default'}. "
            f"Stderr: {process.stderr.strip()}"
        )
        if branch and branch not in [
            "main",
            "master",
        ]:
            logger.info("Attempting to fall back to 'main' branch...")
            return clone_repository(repo_url, target_dir, "main")
        return False


def build_sphinx_vanilla(
    project_slug: str,
    cloned_repo_path: Path,
    doc_source_relative_path: str,
    output_base_dir: Path,
) -> Path | None:
    """Build Sphinx documentation with the project's original theme.

    This function sets up an isolated virtual environment, installs the
    project's dependencies, and runs the standard Sphinx build command
    without applying any DevilDex modifications.

    Args:
    project_slug: A short name for the project, used for naming directories.
    cloned_repo_path: The path to the cloned source code of the project.
    doc_source_relative_path: The relative path within the repo to the
    Sphinx 'source' directory (containing conf.py).
    output_base_dir: The base directory where the build output folder
    will be created.

    Returns:
        The path to the generated documentation directory on success,
            or None on failure.

    """
    logger.info(f"--- Build Sphinx VANILLA per {project_slug} ---")
    doc_source_absolute_path = (cloned_repo_path / doc_source_relative_path).resolve()
    vanilla_output_dir = (output_base_dir / f"{project_slug}_sphinx_vanilla").resolve()
    if not (doc_source_absolute_path / CONF_SPHINX_FILE).exists():
        logger.error(
            f"File conf.py di Sphinx non trovato in {doc_source_absolute_path}"
        )
        return None
    try:
        with IsolatedVenvManager(project_name=f"{project_slug}_sphinx_vanilla") as venv:
            current_tool_specific_packages = SPHINX_COMMON_PACKAGES
            install_conf = InstallConfig(
                project_root_for_install=cloned_repo_path,
                tool_specific_packages=current_tool_specific_packages,
                scan_for_project_requirements=True,
                install_project_editable=True,
            )
            if not install_environment_dependencies(
                venv.pip_executable, f"{project_slug}_vanilla_deps", install_conf
            ):
                logger.error("Dependency installation failed for Sphinx vanilla build.")
                return None
            if vanilla_output_dir.exists():
                shutil.rmtree(vanilla_output_dir)
            vanilla_output_dir.mkdir(parents=True, exist_ok=True)
            sphinx_command = [
                venv.python_executable,
                "-m",
                "sphinx",
                "-b",
                "html",
                str(doc_source_absolute_path),
                str(vanilla_output_dir),
            ]
            logger.info(f"Executing Sphinx vanilla build: {' '.join(sphinx_command)}")
            _stdout, stderr_out, ret_code = execute_command(
                sphinx_command,
                f"Build Sphinx vanilla per {project_slug}",
                cwd=str(doc_source_absolute_path),
            )
            if ret_code == 0 and (vanilla_output_dir / "index.html").exists():
                logger.info(f"Sphinx vanilla build successful: {vanilla_output_dir}")
                return vanilla_output_dir
            else:
                logger.error(
                    f"Sphinx vanilla build failed. RC: {ret_code}\n"
                    f"Stderr:\n{stderr_out}"
                )
                return None
    except (VenvInitializationError, RuntimeError):
        logger.exception("Error during Sphinx vanilla build")
        return None


def _guard_sphinx(
    cloned_repo_path: Path,
    doc_source_relative_path: str,
    output_base_dir: Path,
    project_name: str,
    rebuild: bool = False,
) -> tuple | None:
    original_doc_source_path = (cloned_repo_path / doc_source_relative_path).resolve()
    devil_output_dir = (output_base_dir / f"{project_name}_sphinx_devil").resolve()

    temp_devil_doc_source = output_base_dir / f"{project_name}_temp_devil_docs_src"
    if temp_devil_doc_source.exists() and not rebuild:
        shutil.rmtree(temp_devil_doc_source)
    shutil.copytree(original_doc_source_path, temp_devil_doc_source)
    devil_conf_py_file = temp_devil_doc_source / CONF_SPHINX_FILE

    if not devil_conf_py_file.exists():
        logger.error(
            f"Sphinx conf.py file not found in the temporary copy: {devil_conf_py_file}"
        )
        if temp_devil_doc_source.exists():
            shutil.rmtree(temp_devil_doc_source)
        return None
    return devil_conf_py_file, temp_devil_doc_source, devil_output_dir


def build_sphinx_devil(ctx: BuildContext, doc_source_relative_path: str) -> Path | None:
    """Build Sphinx documentation with the DevilDex theme.

    This function prepares a temporary copy of the documentation source,
    applies the DevilDex theme modifications to its conf.py, sets up an
    isolated virtual environment, and runs the Sphinx build command.

    Args:
        ctx: BuildContext
        doc_source_relative_path: The relative path within the repo to the
            Sphinx 'source' directory (containing conf.py).

    Returns:
        The path to the generated documentation directory on success,
        or None on failure.

    """
    logger.info(f"--- Build Sphinx DEVIL for {ctx.args.project_name} ---")
    devil_conf_py_file, temp_devil_doc_source, devil_output_dir = _guard_sphinx(
        cloned_repo_path=ctx.cloned_repo_path,
        doc_source_relative_path=doc_source_relative_path,
        output_base_dir=ctx.build_outputs_base_dir,
        project_name=ctx.args.project_name,
        rebuild=ctx.args.serve,
    )

    try:
        theme_manager = ThemeManager(
            project_path=ctx.cloned_repo_path,
            doc_type="sphinx",
            sphinx_conf_file=devil_conf_py_file,
        )
        theme_manager.sphinx_change_conf(dev_mode=ctx.args.serve)
        logger.info(f"DevilDex theme applied to: {devil_conf_py_file}")

        with IsolatedVenvManager(
            project_name=f"{ctx.args.project_name}_sphinx_devil"
        ) as venv:
            install_conf = InstallConfig(
                project_root_for_install=ctx.cloned_repo_path,
                tool_specific_packages=SPHINX_COMMON_PACKAGES,
                scan_for_project_requirements=True,
                install_project_editable=True,
            )
            if not install_environment_dependencies(
                venv.pip_executable, f"{ctx.args.project_name}_devil_deps", install_conf
            ):
                logger.error("Dependency installation failed for Sphinx Devil build.")
                if temp_devil_doc_source.exists():
                    shutil.rmtree(temp_devil_doc_source)
                return None

            if devil_output_dir.exists():
                shutil.rmtree(devil_output_dir)
            devil_output_dir.mkdir(parents=True, exist_ok=True)

            sphinx_command = [
                venv.python_executable,
                "-m",
                "sphinx",
                "-b",
                "html",
                "-c",
                str(temp_devil_doc_source),
                str(temp_devil_doc_source),
                str(devil_output_dir),
            ]
            logger.info(f"Executing Sphinx Devil build: {' '.join(sphinx_command)}")
            _stdout, stderr_out, ret_code = execute_command(
                sphinx_command,
                f"Build Sphinx Devil for {ctx.args.project_name}",
                cwd=str(temp_devil_doc_source),
            )

            if temp_devil_doc_source.exists():
                shutil.rmtree(temp_devil_doc_source)

            if ret_code == 0 and (devil_output_dir / "index.html").exists():
                logger.info(f"Sphinx Devil build successful: {devil_output_dir}")
                return devil_output_dir
            else:
                logger.error(
                    f"Sphinx Devil build failed. RC: {ret_code}\nStderr:\n{stderr_out}"
                )
                return None
    except (VenvInitializationError, RuntimeError):
        logger.exception("Error during Sphinx Devil build")
        if temp_devil_doc_source.exists():
            shutil.rmtree(temp_devil_doc_source)
        return None


def build_pdoc3_vanilla(
    project_slug: str,
    cloned_repo_path: Path,
    module_name: str,
    output_base_dir: Path,
) -> Path | None:
    """Build pdoc3 documentation with its default theme.

    This function generates HTML documentation from a Python module using
    pdoc3's standard, built-in templates. It does not apply any DevilDex
    customizations.

    Args:
        project_slug: A short name for the project, used for naming directories.
        cloned_repo_path: The path to the cloned source code of the project.
        module_name: The name of the Python module to document.
        output_base_dir: The base directory where the build output folder
            will be created.

    Returns:
        The path to the generated documentation directory on success,
        or None on failure.

    """
    logger.info(
        f"--- Building pdoc3 VANILLA for {project_slug} (module: {module_name}) ---"
    )
    vanilla_output_dir = (output_base_dir / f"{project_slug}_pdoc3_vanilla").resolve()
    temp_pdoc_build_target = (
        output_base_dir / f"{project_slug}_pdoc3_vanilla_temp_build"
    )

    doc_generator = DocStringsSrc(template_dir=None)
    result_path_str = doc_generator.generate_docs_from_folder(
        project_name=module_name,
        input_folder=str(cloned_repo_path.resolve()),
        output_folder=str(temp_pdoc_build_target.resolve()),
    )

    if isinstance(result_path_str, str):
        if vanilla_output_dir.exists():
            shutil.rmtree(vanilla_output_dir)
        shutil.move(result_path_str, vanilla_output_dir)
        logger.info(f"pdoc3 vanilla build successful: {vanilla_output_dir}")
        if temp_pdoc_build_target.exists() and not any(
            temp_pdoc_build_target.iterdir()
        ):
            shutil.rmtree(temp_pdoc_build_target)
        return vanilla_output_dir
    else:
        logger.error("pdoc3 vanilla build failed.")
        if temp_pdoc_build_target.exists():
            shutil.rmtree(temp_pdoc_build_target)
        return None


def build_pdoc3_devil(
    project_slug: str,
    cloned_repo_path: Path,
    module_name: str,
    output_base_dir: Path,
) -> Path | None:
    """Build pdoc3 documentation with the DevilDex theme.

    This function generates HTML documentation from a Python module using
    a custom DevilDex template directory to override the default pdoc3 look
    and feel.

    Args:
        project_slug: A short name for the project, used for naming directories.
        cloned_repo_path: The path to the cloned source code of the project.
        module_name: The name of the Python module to document.
        output_base_dir: The base directory where the build output folder
            will be created.

    Returns:
        The path to the generated documentation directory on success,
        or None on failure.

    """
    logger.info(
        f"--- Building pdoc3 DEVIL for {project_slug} (module: {module_name}) ---"
    )
    devil_output_dir = (output_base_dir / f"{project_slug}_pdoc3_devil").resolve()
    temp_pdoc_build_target = output_base_dir / f"{project_slug}_pdoc3_devil_temp_build"

    doc_generator = DocStringsSrc(template_dir=PDOC3_DEVILDEX_THEME_PATH)
    result_path_str = doc_generator.generate_docs_from_folder(
        project_name=module_name,
        input_folder=str(cloned_repo_path.resolve()),
        output_folder=str(temp_pdoc_build_target.resolve()),
    )

    if isinstance(result_path_str, str):
        if devil_output_dir.exists():
            shutil.rmtree(devil_output_dir)
        shutil.move(result_path_str, devil_output_dir)
        logger.info(f"pdoc3 Devil build successful: {devil_output_dir}")
        if temp_pdoc_build_target.exists() and not any(
            temp_pdoc_build_target.iterdir()
        ):
            shutil.rmtree(temp_pdoc_build_target)
        return devil_output_dir
    else:
        logger.error("pdoc3 Devil build failed.")
        if temp_pdoc_build_target.exists():
            shutil.rmtree(temp_pdoc_build_target)
        return None


def build_mkdocs_vanilla(
    project_slug: str,
    cloned_repo_path: Path,
    output_base_dir: Path,
    version_id: str = "vanilla",
) -> Path | None:
    """Build MkDocs documentation with its original configuration.

    This function runs the standard MkDocs build process for a project
    without applying any DevilDex theme modifications. It uses a temporary
    directory for the build process and moves the final site to a
    version-specific output folder.

    Args:
        project_slug: A short name for the project, used for naming directories.
        cloned_repo_path: The path to the cloned source code of the project.
        output_base_dir: The base directory where the build output folder
            will be created.
        version_id: A string identifier for this build version.

    Returns:
        The path to the generated documentation directory on success,
        or None on failure.

    """
    logger.info(f"--- Building MkDocs VANILLA for {project_slug} ---")
    vanilla_output_dir = (output_base_dir / f"{project_slug}_mkdocs_vanilla").resolve()
    temp_base_for_mkdocs_build = (
        output_base_dir / f"{project_slug}_mkdocs_vanilla_temp_base"
    )

    built_path_str = process_mkdocs_source_and_build(
        source_project_path=str(cloned_repo_path.resolve()),
        project_slug=project_slug,
        version_identifier=version_id,
        base_output_dir=temp_base_for_mkdocs_build,
    )
    if built_path_str:
        if vanilla_output_dir.exists():
            shutil.rmtree(vanilla_output_dir)
        shutil.move(built_path_str, vanilla_output_dir)
        logger.info(f"MkDocs vanilla build successful: {vanilla_output_dir}")
        if temp_base_for_mkdocs_build.exists():
            shutil.rmtree(temp_base_for_mkdocs_build)
        return vanilla_output_dir
    else:
        logger.error("MkDocs vanilla build failed.")
        if temp_base_for_mkdocs_build.exists():
            shutil.rmtree(temp_base_for_mkdocs_build)
        return None


def build_mkdocs_devil(
    project_slug: str,
    cloned_repo_path: Path,
    output_base_dir: Path,
    version_id: str = "devil",
) -> Path | None:
    """Build MkDocs documentation (placeholder for the DevilDex theme).

    Note: This function currently performs a standard MkDocs build and does
    not yet apply a specific DevilDex theme. It serves as a placeholder
    for future theme integration.

    Args:
        project_slug: A short name for the project, used for naming directories.
        cloned_repo_path: The path to the cloned source code of the project.
        output_base_dir: The base directory where the build output folder
            will be created.
        version_id: A string identifier for this build version.

    Returns:
        The path to the generated documentation directory on success,
        or None on failure.

    """
    logger.info(f"--- Building MkDocs DEVIL for {project_slug} ---")
    devil_output_dir = (output_base_dir / f"{project_slug}_mkdocs_devil").resolve()
    temp_base_for_mkdocs_build = (
        output_base_dir / f"{project_slug}_mkdocs_devil_temp_base"
    )
    logger.warning(
        "The MkDocs Devil build does not yet apply a specific DevilDex theme. "
        "It is performing a standard build as a placeholder."
    )
    built_path_str = process_mkdocs_source_and_build(
        source_project_path=str(cloned_repo_path.resolve()),
        project_slug=project_slug,
        version_identifier=version_id,
        base_output_dir=temp_base_for_mkdocs_build,
    )
    if built_path_str:
        if devil_output_dir.exists():
            shutil.rmtree(devil_output_dir)
        shutil.move(built_path_str, devil_output_dir)
        logger.info(f"MkDocs Devil (standard) build successful: {devil_output_dir}")
        if temp_base_for_mkdocs_build.exists():
            shutil.rmtree(temp_base_for_mkdocs_build)
        return devil_output_dir
    else:
        logger.error("MkDocs Devil (standard) build failed.")
        if temp_base_for_mkdocs_build.exists():
            shutil.rmtree(temp_base_for_mkdocs_build)
        return None


def find_entry_point(
    built_docs_path: Path, doc_type: str, module_name_for_pdoc: str | None = None
) -> Path | None:
    """Find entry point file (e.g., index.html) in a built documentation directory.

    This function searches for a suitable starting HTML file in a given build
    output directory. It prioritizes `index.html`, but includes specific
    fallback logic for different documentation types (like pdoc3) and a
    general fallback to any available HTML file if the primary ones are not
    found.

    Args:
        built_docs_path: The path to the root of the built documentation site.
        doc_type: The type of documentation ("sphinx", "pdoc3", etc.) to
            inform search logic.
        module_name_for_pdoc: The name of the module, used specifically for
            finding the entry point in pdoc3 builds.

    Returns:
        The Path to the entry point HTML file, or None if no suitable file
        is found.

    """
    if not built_docs_path.exists():
        return None

    index_html = built_docs_path / "index.html"
    if index_html.is_file():
        return index_html

    if doc_type == "pdoc3" and module_name_for_pdoc:
        module_html = built_docs_path / f"{module_name_for_pdoc}.html"
        if module_html.is_file():
            return module_html
    logger.warning(
        f"index.html file not found in {built_docs_path} for type {doc_type}."
    )
    html_files = list(built_docs_path.glob("*.html"))
    if html_files:
        logger.info(f"Found an alternative HTML file as a fallback: {html_files[0]}")
        return html_files[0]
    return None


def run_server_mode(base_context: BuildContext) -> None:
    """Manage the live-reloading server workflow.

    This function handles the `--serve` mode. It performs an initial 'devil'
    build, opens the result in a web browser, and then starts a local
    web server. The server is configured with a live-reload mechanism that
    triggers a new build whenever a request is made to the rebuild endpoint.

    Args:
        base_context: The initial BuildContext containing the configuration
            for the build process.

    """
    logger.info("Performing initial DEVIL build for the server...")
    initial_ctx = replace(base_context, build_id=datetime.now().strftime("%H:%M:%S"))
    _, devil_entry_point = _perform_builds(ctx=initial_ctx)

    if devil_entry_point:
        (devil_entry_point.parent / "_build_signal.txt").write_text(
            initial_ctx.build_id
        )
        server_url = f"http://localhost:{SERVER_PORT}/{devil_entry_point.name}"
        logger.info(f"Opening DEVIL documentation at: {server_url}")
        webbrowser.open_new(server_url)
        rebuilder = ServerRebuilder(base_context)

        start_server(
            build_dir=devil_entry_point.parent,
            rebuild_callback=rebuilder.rebuild,
            port=SERVER_PORT,
        )
    else:
        logger.error("Initial DEVIL build failed. Cannot start the server.")


def pdoc3_run(ctx: BuildContext) -> tuple[Path | None, Path | None] | None:
    """Run pdoc3 build."""
    vanilla_entry_point: Path | None = None
    devil_entry_point: Path | None = None
    module_name = ctx.project_config.get("module_name")

    if not module_name:
        logger.error(
            f"'module_name' configuration is missing for pdoc3 "
            f"for project {ctx.args.project_name}"
        )
        return None, None
    if not ctx.args.skip_vanilla:
        vanilla_built_path = build_pdoc3_vanilla(
            ctx.args.project_name,
            ctx.cloned_repo_path,
            module_name,
            ctx.build_outputs_base_dir,
        )
        if vanilla_built_path:
            vanilla_entry_point = find_entry_point(
                vanilla_built_path, "pdoc3", module_name
            )
    if not ctx.args.skip_devil:
        devil_built_path = build_pdoc3_devil(
            ctx.args.project_name,
            ctx.cloned_repo_path,
            module_name,
            ctx.build_outputs_base_dir,
        )
        if devil_built_path:
            devil_entry_point = find_entry_point(devil_built_path, "pdoc3", module_name)
    return vanilla_entry_point, devil_entry_point


def mkdocs_run(ctx: BuildContext) -> tuple[str | None, str | None]:
    """Run mkdocs build."""
    vanilla_entry_point: Path | None = None
    devil_entry_point: Path | None = None
    if not ctx.args.skip_vanilla:
        vanilla_built_path = build_mkdocs_vanilla(
            ctx.args.project_name,
            ctx.cloned_repo_path,
            ctx.build_outputs_base_dir,
            version_id=ctx.branch_to_clone,
        )
        if vanilla_built_path:
            vanilla_entry_point = find_entry_point(vanilla_built_path, "mkdocs")
    if not ctx.args.skip_devil:
        devil_built_path = build_mkdocs_devil(
            ctx.args.project_name,
            ctx.cloned_repo_path,
            ctx.build_outputs_base_dir,
            version_id=ctx.branch_to_clone,
        )
        if devil_built_path:
            devil_entry_point = find_entry_point(devil_built_path, "mkdocs")
    return vanilla_entry_point, devil_entry_point


def sphinx_run(ctx: BuildContext) -> tuple[Path | None, Path | None] | None:
    """Run Sphinx build."""
    vanilla_entry_point: Path | None = None
    devil_entry_point: Path | None = None
    doc_source_rel = ctx.project_config.get("doc_source_path_relative", "docs/")
    if not ctx.args.skip_vanilla:
        vanilla_built_path = build_sphinx_vanilla(
            ctx.args.project_name,
            ctx.cloned_repo_path,
            doc_source_rel,
            ctx.build_outputs_base_dir,
        )
        if vanilla_built_path:
            vanilla_entry_point = find_entry_point(vanilla_built_path, "sphinx")
    if not ctx.args.skip_devil:
        devil_built_path = build_sphinx_devil(
            ctx=ctx, doc_source_relative_path=doc_source_rel
        )
        if devil_built_path:
            devil_entry_point = find_entry_point(devil_built_path, "sphinx")
    return vanilla_entry_point, devil_entry_point


def _perform_builds(
    ctx: BuildContext,
) -> tuple[Path | None, Path | None]:
    """Dispatch the build to the correct handler based on doc type."""
    doc_type_to_build = ctx.args.doc_type or ctx.project_config["doc_type"]

    vanilla_entry_point: Path | None = None
    devil_entry_point: Path | None = None

    if doc_type_to_build == "sphinx":
        vanilla_entry_point, devil_entry_point = sphinx_run(ctx=ctx)
    elif doc_type_to_build == "pdoc3":
        vanilla_entry_point, devil_entry_point = pdoc3_run(ctx=ctx)
    elif doc_type_to_build == "mkdocs":
        vanilla_entry_point, devil_entry_point = mkdocs_run(ctx=ctx)
    else:
        logger.error(f"Unsupported documentation type: {doc_type_to_build}")
    return vanilla_entry_point, devil_entry_point


def setup_environment(args: Namespace) -> BuildContext | None:
    """Prepare the build environment and creates the main BuildContext.

    This function orchestrates the initial setup. It validates the project,
    clones the source repository into a temporary directory, creates the
    necessary build output folders, and consolidates all configuration and
    paths into a BuildContext object. It also handles the specific logic
    for setting the output path for server mode (`--serve`).

    Args:
        args: The parsed command-line arguments.

    Returns:
        A fully populated BuildContext object ready for the build process,
        or None if the setup fails (e.g., project not found, or repository
        clone fails).

    """
    project_config = KNOWN_PROJECTS.get(args.project_name)
    if not project_config:
        logger.error(f"Project '{args.project_name}' not found in KNOWN_PROJECTS.")
        return None

    res = _guards(args=args, project_config=project_config)
    if not res:
        return None

    (
        doc_type_to_build,
        build_outputs_base_dir_from_guard,
        cloned_repo_path,
        run_temp_dir,
        branch_to_clone,
    ) = res

    if args.serve:
        final_build_outputs_dir = FIXED_BUILD_OUTPUT_DIR / args.project_name
        if final_build_outputs_dir.exists():
            shutil.rmtree(final_build_outputs_dir)
        final_build_outputs_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Server mode: Outputting to {final_build_outputs_dir}")
        args.skip_vanilla = True
    else:
        final_build_outputs_dir = build_outputs_base_dir_from_guard

    return BuildContext(
        project_config=project_config,
        args=args,
        cloned_repo_path=cloned_repo_path,
        build_outputs_base_dir=final_build_outputs_dir,
        run_temp_dir=run_temp_dir,
        branch_to_clone=branch_to_clone,
    )


def run_single_build_mode(base_context: BuildContext) -> None:
    """Manage the single-build workflow and opens the results."""
    vanilla_entry_point, devil_entry_point = _perform_builds(ctx=base_context)

    if vanilla_entry_point and vanilla_entry_point.exists():
        logger.info(f"Opening VANILLA documentation: {vanilla_entry_point.as_uri()}")
        webbrowser.open_new(vanilla_entry_point.as_uri())
    elif not base_context.args.skip_vanilla:
        logger.warning("Vanilla documentation entry point not found or build failed.")

    if devil_entry_point and devil_entry_point.exists():
        logger.info(f"Opening DEVIL documentation: {devil_entry_point.as_uri()}")
        webbrowser.open_new(devil_entry_point.as_uri())
    elif not base_context.args.skip_devil:
        logger.warning("Devil documentation entry point not found or build failed.")


def main() -> None:
    """Entry point: Orchestrates environment setup and build execution."""
    parser = _configure_arg_parser()
    args = parser.parse_args()

    if args.only == "devil":
        args.skip_vanilla = True
    elif args.only == "vanilla":
        args.skip_devil = True

    build_context = setup_environment(args)
    if not build_context:
        logger.error("Environment setup failed. Aborting.")
        return

    try:
        if args.serve:
            run_server_mode(build_context)
        else:
            run_single_build_mode(build_context)
    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt received. Exiting...")
    finally:
        if not args.keep_builds and build_context.run_temp_dir.exists():
            logger.info(
                f"Cleaning up temporary directory: {build_context.run_temp_dir}"
            )
            shutil.rmtree(build_context.run_temp_dir)

    logger.info("Theme comparison script finished.")


def _configure_arg_parser() -> argparse.ArgumentParser:
    """Configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Compare original and DevilDex documentation themes."
    )
    parser.add_argument(
        "project_name",
        choices=list(KNOWN_PROJECTS.keys()),
        help="Name of the project to process (must be in KNOWN_PROJECTS).",
    )
    parser.add_argument(
        "--doc-type",
        choices=SUPPORTED_TYPES,
        help="Force a specific documentation type, overriding the project's default.",
    )
    parser.add_argument(
        "--branch",
        help="Specific branch to clone. Defaults to the project's default or 'main'.",
    )
    parser.add_argument(
        "--keep-builds",
        action="store_true",
        help="Keep temporary build folders after execution.",
    )

    build_group = parser.add_mutually_exclusive_group()
    build_group.add_argument(
        "--only",
        choices=["vanilla", "devil"],
        help="Only run the specified build (vanilla or devil).",
    )
    build_group.add_argument(
        "--skip-vanilla",
        action="store_true",
        help="Skip the vanilla documentation build.",
    )
    build_group.add_argument(
        "--skip-devil",
        action="store_true",
        help="Skip the DevilDex documentation build.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start a live-reload server after the 'devil' build.",
    )
    return parser


def _guards(args: Namespace, project_config: dict) -> tuple | None:
    if not project_config:
        logger.error(f"Project '{args.project_name}' not found in KNOWN_PROJECTS.")
        return None

    doc_type_to_build = args.doc_type or project_config["doc_type"]
    repo_url = project_config["repo_url"]
    branch_to_clone = args.branch or project_config.get("default_branch", "main")

    run_temp_dir = Path(tempfile.mkdtemp(prefix=f"theme_compare_{args.project_name}_"))
    logger.info(f"Temporary directory for this run: {run_temp_dir}")

    cloned_repo_path = run_temp_dir / "source_clone"
    build_outputs_base_dir = run_temp_dir / "build_outputs"
    build_outputs_base_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Cloning {args.project_name} from {repo_url} (branch: {branch_to_clone})"
    )
    if not clone_repository(repo_url, cloned_repo_path, branch_to_clone):
        logger.error("Repository clone failed. Aborting.")
        if not args.keep_builds:
            shutil.rmtree(run_temp_dir)
        return None
    return (
        doc_type_to_build,
        build_outputs_base_dir,
        cloned_repo_path,
        run_temp_dir,
        branch_to_clone,
    )


if __name__ == "__main__":
    main()
