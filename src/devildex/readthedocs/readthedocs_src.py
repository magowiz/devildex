"""readthedocs source handling module."""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests

from devildex.info import PROJECT_ROOT
from devildex.theming.manager import ThemeManager
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command,
    install_project_and_dependencies_in_venv,
)

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s"
    )

CONF_SPHINX_FILE = "conf.py"
GIT_FULL_PATH = shutil.which('git')

def find_doc_source_in_clone(repo_path: Path) -> Path:
    """Identify the documentation source directory within a cloned repository.

    It does NOT copy any files.

    Args:
        repo_path (str): The local path to the cloned repository.

    Returns:
        str: The path to the documentation source directory (containing conf.py),
             or None if not found.

    """
    print(f"\nSearching for documentation source directory in: {repo_path}")
    potential_doc_dirs = ["docs", "doc", "Doc"]
    doc_source_path = _find_doc_dir_in_repo(repo_path, potential_doc_dirs)
    if not doc_source_path:
        print("No documentation source directory with conf.py found in the clone.")
        return None
    print(f"Documentation source directory identified at: {doc_source_path}")
    return doc_source_path


def _find_doc_dir_in_repo(repo_path: str, potential_doc_dirs: list) -> str:
    """Find the first potential documentation directory that contains a conf.py file.

    Also checks the repository root if no specific doc directory is found.

    Args:
        repo_path (str): The local path to the cloned repository.
        potential_doc_dirs (list): A list of potential directory names
                                   for documentation (e.g., ["docs", "doc"]).

    Returns:
        str: The path to the documentation source directory (containing conf.py),
             or None if not found.

    """
    for doc_dir_name in potential_doc_dirs:
        current_path = os.path.join(repo_path, doc_dir_name)
        if os.path.isdir(current_path) and os.path.exists(
            os.path.join(current_path, CONF_SPHINX_FILE)
        ):
            print(
                "Found documentation source directory with conf.py: " f"{current_path}"
            )
            return current_path
        if os.path.isdir(current_path):
            print(
                f"Found directory '{current_path}', but no conf.py. "
                "Continuing search..."
            )
    if os.path.exists(os.path.join(repo_path, CONF_SPHINX_FILE)):
        print(f"Found conf.py in the repository root: {repo_path}")
        return repo_path

    print(
        "Fallback: Searching for conf.py recursively in the entire"
        f"repository: {repo_path}..."
    )
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [
            d
            for d in dirs
            if d
            not in [
                ".git",
                ".hg",
                ".svn",
                "venv",
                ".venv",
                "env",
                "__pycache__",
                "node_modules",
                "build",
                "dist",
                "docs/_build",
                "site",
            ]
        ]
        if CONF_SPHINX_FILE in files:
            conf_file_path = os.path.join(root, CONF_SPHINX_FILE)
            doc_source_dir = root
            print(
                "Found conf.py via full recursive search at: "
                f"{conf_file_path} (source directory: {doc_source_dir})"
            )
            return doc_source_dir
    return None


def _find_sphinx_doc_requirements_file(
    source_dir_path: Path, clone_root_path: Path, project_slug: str
) -> Path | None:
    """Cerca il file dei requisiti specifici per la documentazione di Sphinx."""
    candidate_req_paths = [
        source_dir_path / "requirements.txt",
        source_dir_path.parent / "requirements.txt",
        clone_root_path / "doc-requirements.txt",
        clone_root_path / "docs-requirements.txt",
        clone_root_path / "dev-requirements.txt",
        clone_root_path / "requirements-doc.txt",
        clone_root_path / "requirements-docs.txt",
        clone_root_path / "requirements-dev.txt",
        clone_root_path / "requirements.txt",
        clone_root_path / "docs" / "requirements.txt",
        clone_root_path / "doc" / "requirements.txt",
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


@dataclass
class SphinxBuildContext:
    """Holds context and paths for a Sphinx build operation."""

    source_dir: Path
    clone_root: Path
    doc_requirements_file: Path | None
    project_install_root: Path
    project_slug: str
    version_identifier: str
    base_output_dir: Path

    @property
    def conf_py_file(self) -> Path:
        """Path to the conf.py file within the source directory."""
        return self.source_dir / CONF_SPHINX_FILE

    @property
    def final_output_dir(self) -> Path:
        """The final, resolved path for the Sphinx HTML output."""
        return (
            Path(self.base_output_dir) / self.project_slug / self.version_identifier
        ).resolve()


def build_sphinx_docs(
    isolated_source_path: str,
    project_slug: str,
    version_identifier: str,
    original_clone_dir_path: str,
    base_output_dir: Path,
) -> str | None:
    """Execute sphinx-build in a temporary, isolated virtual environment."""
    logger.info(
        "\n--- Starting Isolated Sphinx Build for %s v%s ---",
        project_slug,
        version_identifier,
    )
    source_dir_p = Path(isolated_source_path)
    clone_root_p = Path(original_clone_dir_path)
    sctx = SphinxBuildContext(
        source_dir=source_dir_p,
        clone_root=clone_root_p,
        doc_requirements_file=_find_sphinx_doc_requirements_file(
            source_dir_p, clone_root_p, project_slug
        ),
        project_install_root=clone_root_p,
        project_slug=project_slug,
        version_identifier=version_identifier,
        base_output_dir=base_output_dir,
    )
    if not sctx.conf_py_file.exists():
        logger.error("Critical Error: conf.py not found in %s.", sctx.source_dir)
        return None
    logger.info("Sphinx HTML output directory: %s", sctx.final_output_dir)
    try:
        if sctx.final_output_dir.exists():
            logger.info("Removing existing output directory: %s", sctx.final_output_dir)
            shutil.rmtree(sctx.final_output_dir)
        sctx.final_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(
            "Error creating/cleaning output directory %s: %s", sctx.final_output_dir, e
        )
        return None
    build_successful = False
    try:
        with IsolatedVenvManager(
            project_name=f"{sctx.project_slug}-{sctx.version_identifier}"
        ) as venv:
            install_success = install_project_and_dependencies_in_venv(
                pip_executable=venv.pip_executable,
                project_name=sctx.project_slug,
                project_root_for_install=sctx.project_install_root,
                doc_requirements_path=sctx.doc_requirements_file,
                base_packages_to_install=[
                    "sphinx",
                    "pallets-sphinx-themes",
                    "sphinxcontrib.log-cabinet",
                    "sphinx-tabs",
                ],
            )
            if not install_success:
                logger.error(
                    "CRITICAL: Installation of project/dependencies (including Sphinx) "
                    "for %s FAILED or had critical issues. Aborting Sphinx build.",
                    sctx.project_slug,
                )
                return None
            sphinx_command_list = [
                venv.python_executable,
                "-m",
                "sphinx",
                "-b",
                "html",
                ".",
                str(sctx.final_output_dir),
            ]
            sphinx_process_env = {"LC_ALL": "C"}
            logger.info("Executing Sphinx: %s", " ".join(sphinx_command_list))
            stdout, stderr, returncode = execute_command(
                sphinx_command_list,
                f"Sphinx build for {sctx.project_slug}",
                cwd=sctx.source_dir,
                env=sphinx_process_env,
            )
            if returncode == 0:
                logger.info(
                    "Sphinx build for %s completed successfully.", sctx.project_slug
                )
                build_successful = True
            else:
                logger.error(
                    "Sphinx build for %s failed. Return code: %s",
                    sctx.project_slug,
                    returncode,
                )
                logger.error("Sphinx stdout:\n%s", stdout)
                logger.error("Sphinx stderr:\n%s", stderr)

    except RuntimeError as e:
        logger.error(
            "Critical error during isolated build setup for %s: %s",
            sctx.project_slug,
            e,
        )
    except OSError as e:
        logger.error(
            "Error creating/cleaning output directory %s: %s", sctx.final_output_dir, e
        )
        return None
    finally:
        logger.info("--- Finished Isolated Sphinx Build for %s ---", sctx.project_slug)
    return str(sctx.final_output_dir) if build_successful else None


def _cleanup(clone_dir_path: Path) -> None:
    if os.path.exists(clone_dir_path):
        print(f"\nDeleting repository cloned directory: {clone_dir_path}")
        try:
            shutil.rmtree(clone_dir_path)
            print("Delete completed.")
        except OSError as e:
            print(
                "Error during deleting della repository cloned "
                f"'{clone_dir_path}': {e}"
            )


def _extract_repo_url_branch(api_project_detail_url: str, project_slug: str) -> tuple[str, str]:
    repo_url = None
    default_branch = "main"
    try:
        response = requests.get(api_project_detail_url, timeout=60)
        response.raise_for_status()
        project_data = response.json()
        repo_data = project_data.get("repository")
        if repo_data:
            repo_url = repo_data.get("url")
        default_branch = project_data.get("default_branch", default_branch)

        if not repo_url:
            print(
                "Warning: URL del repository sources non trovato per "
                f"'{project_slug}' using API."
            )
        else:
            print(f"Trovato URL repository: {repo_url}")
            print(f"Branch di default (used come version identifier): {default_branch}")
    except requests.exceptions.RequestException as e:
        print(f"Warning: Error durante la richiesta API: {e}")
        print("Provo a search la repository cloned locally if already exists.")
    return default_branch, repo_url


def run_clone(repo_url: str, default_branch: str, clone_dir_path: Path, bzr: bool) -> tuple[str|None, str|None]| str:
    """Perform a clone for matching vcs."""
    successful_clone = False
    print(f"Cloning repository (branch '{default_branch}') in: {clone_dir_path}")
    fallback_branches = ["master", "main"]
    cmd_git = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        default_branch,
        repo_url,
        clone_dir_path,
    ]
    cmd_bzr = ["bzr", "branch", repo_url, str(clone_dir_path)]
    try:
        if not bzr:
            result = subprocess.run(  # noqa: S603
                cmd_git,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode == 0:
                successful_clone = True
            if result.returncode != 0:
                for default_branch in fallback_branches:  # pylint: disable=R1704  # noqa: PLR1704
                    shutil.rmtree(clone_dir_path, ignore_errors=True)
                    result = subprocess.run(  # noqa: S603
                        [
                            GIT_FULL_PATH,
                            "clone",
                            "--depth",
                            "1",
                            "--branch",
                            default_branch,
                            repo_url,
                            str(clone_dir_path),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                    )
                    if result.returncode == 0:
                        successful_clone = True
                        break
        else:
            result = subprocess.run(  # noqa: S603
                cmd_bzr,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode == 0:
                successful_clone = True
        print("git clone Command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error during execution of git clone command:\n{e.stderr}")
        return None, None
    except FileNotFoundError:
        print("Error: 'git' command not found. Be sure that Git is installed.")
        return None, None
    if not successful_clone:
        return None, None
    return (
        default_branch
        if default_branch and default_branch.lower() != "unknown"
        else "trunk"
    )


def _attempt_clone_and_process_result(
    repo_url: str,
    initial_default_branch: str,
    clone_dir_path: Path,
    bzr: bool,
    project_slug: str,
) -> tuple[bool, str]:
    """Tenta di clonare il repository e processa il risultato.

    Restituisce (successo_clone, branch_effettivo_post_tentativo).
    """
    run_clone_result = run_clone(repo_url, initial_default_branch, clone_dir_path, bzr)

    if isinstance(run_clone_result, str):
        current_effective_branch = run_clone_result
        logger.info(
            "Cloning successful for '%s'. Effective branch: '%s'. Path: '%s'",
            project_slug,
            current_effective_branch,
            clone_dir_path,
        )
        return True, current_effective_branch
    if isinstance(run_clone_result, tuple) and run_clone_result == (None, None):
        logger.error(
            "Cloning failed for '%s' due to command error (details in previous logs).",
            project_slug,
        )
        return False, initial_default_branch
    logger.error(
        "Cloning attempt for '%s' resulted in an unexpected state or failure. "
        "Result: %s",
        project_slug,
        run_clone_result,
    )
    return False, initial_default_branch


def _handle_repository_cloning(
    repo_url: str | None,
    initial_default_branch: str,
    base_output_dir: Path,
    project_slug: str,
    bzr: bool,
) -> tuple[Path | None, str]:
    """Gestisce la logica di clonazione del repository.

    Restituisce il percorso del clone e il branch effettivo utilizzato.
    """
    clone_dir_name = f"{project_slug}_repo_{initial_default_branch}"
    clone_dir_path = base_output_dir / clone_dir_name
    effective_branch = initial_default_branch
    cloned_repo_exists_before = clone_dir_path.exists()
    if repo_url and not cloned_repo_exists_before:
        logger.info(
            "Repository for '%s' not found locally at '%s'. Attempting to clone.",
            project_slug,
            clone_dir_path,
        )
        _, branch_after_attempt = _attempt_clone_and_process_result(
            repo_url, initial_default_branch, clone_dir_path, bzr, project_slug
        )
        effective_branch = branch_after_attempt
    elif repo_url and cloned_repo_exists_before:
        logger.info(
            "Repository for '%s' already exists at '%s'. Skipping clone.",
            project_slug,
            clone_dir_path,
        )
    elif not repo_url:
        logger.warning(
            "No repository URL provided for '%s'. Cannot clone.", project_slug
        )
        if not cloned_repo_exists_before:
            logger.error(
                "No repository URL and no existing clone for '%s'.", project_slug
            )
            return None, effective_branch
    if clone_dir_path.exists():
        logger.info("Using repository for '%s' at: '%s'", project_slug, clone_dir_path)
        return clone_dir_path, effective_branch
    logger.error(
        "Repository directory for '%s' not found at '%s' after processing.",
        project_slug,
        clone_dir_path,
    )
    return None, effective_branch


@dataclass
class ProjectContext:
    """Project context."""

    slug: str
    version: str


def _process_documentation(
    clone_dir_path: Path,
    project_ctx: ProjectContext,
    base_output_dir: Path | None = None,
) -> tuple[str | None, str | None]:
    """Isolate documentation source, apply customizations and build it."""
    logger.info(
        "Processing documentation for '%s' (version: %s) from '%s'",
        project_ctx.slug,
        project_ctx.version,
        clone_dir_path,
    )
    isolated_source_path = find_doc_source_in_clone(str(clone_dir_path))
    build_output_path = None
    if isolated_source_path:
        logger.info(
            "Documentation source for '%s' isolated at: %s",
            project_ctx.slug,
            isolated_source_path,
        )
        isolated_source_path_p = Path(isolated_source_path)
        conf_py_file = isolated_source_path_p / CONF_SPHINX_FILE
        theme_manager = ThemeManager(
            project_path=clone_dir_path,
            doc_type="sphinx",
            sphinx_conf_file=conf_py_file,
        )
        theme_manager.sphinx_change_conf()
        build_output_path = build_sphinx_docs(
            isolated_source_path,
            project_ctx.slug,
            project_ctx.version,
            str(clone_dir_path),
            base_output_dir=base_output_dir,
        )
    else:
        logger.warning(
            "Documentation source isolation failed for '%s' (path: '%s'). "
            "Skipping Sphinx build.",
            project_ctx.slug,
            clone_dir_path,
        )
    return isolated_source_path, build_output_path


def download_readthedocs_source_and_build(
    project_name: str,
    project_url: str,
    existing_clone_path: str | None = None,
    output_dir: Path | None = None,
    clone_base_dir_override: Path | None = None,
) -> tuple[str | None, str | None]:
    """Scarica sorgenti da RTD, clona, isola sorgenti doc, esegue Sphinx e pulisce."""
    logger.info(
        "\n--- Starting RTD Source Download, Build & Cleanup for: %s ---", project_name
    )
    logger.info("Project URL: %s", project_url)

    project_slug = project_name
    if not project_slug:
        logger.error("Project slug (project_name) cannot be empty.")
        return None, None

    logger.info("Project Slug: %s", project_slug)
    api_project_detail_url = f"https://readthedocs.org/api/v3/projects/{project_slug}/"
    logger.info("Fetching project details from API: %s", api_project_detail_url)

    initial_default_branch, repo_url = _extract_repo_url_branch(
        api_project_detail_url, project_slug
    )
    if clone_base_dir_override:
        base_output_dir = clone_base_dir_override
    else:
        base_output_dir = PROJECT_ROOT / "rtd_source_clones_temp"
    base_output_dir.mkdir(parents=True, exist_ok=True)

    bzr = bool(repo_url and repo_url.startswith("lp:"))
    clone_dir_path: Path | None
    effective_branch: str
    if existing_clone_path and Path(existing_clone_path).exists():
        logger.info("Using existing clone path: %s", existing_clone_path)
        clone_dir_path = Path(existing_clone_path)
        effective_branch = initial_default_branch
    else:
        clone_dir_path, effective_branch = _handle_repository_cloning(
            repo_url, initial_default_branch, base_output_dir, project_slug, bzr
        )

    if not clone_dir_path:
        logger.error(
            "Failed to obtain a valid repository clone for '%s'.", project_slug
        )
        return _download_handle_result(None, None)

    project_context = ProjectContext(slug=project_slug, version=effective_branch)
    if output_dir:
        final_sphinx_build_destination = output_dir
    else:
        final_sphinx_build_destination = (
            PROJECT_ROOT / "devildex_sphinx_build_output_default"
        )  # Puoi scegliere un nome diverso
    isolated_source_path, build_output_path = _process_documentation(
        clone_dir_path,
        project_context,
        base_output_dir=final_sphinx_build_destination,
    )

    _cleanup(str(clone_dir_path))
    return _download_handle_result(isolated_source_path, build_output_path)


def _download_handle_result(isolated_source_path: Path, build_output_path: Path)-> tuple[Path|None, Path|None]:
    if isolated_source_path and build_output_path:
        print(f"\nIsolated source documentation in: {isolated_source_path}")
        print(f"Build HTML Sphinx generata in:    {build_output_path}")
        return isolated_source_path, build_output_path
    if isolated_source_path:
        print(f"\nIsolated Sources documentation in: {isolated_source_path}")
        print("Failed Build Sphinx.")
        return isolated_source_path, None
    print("\nFailed Isolating sources and build Sphinx.")
    return None, None


if __name__ == "__main__":
    PROJECT_NAME_EXAMPLE = "black"
    PROJECT_URL_EXAMPLE = "https://github.com/psf/black"
    _, _ = download_readthedocs_source_and_build(
        project_name=PROJECT_NAME_EXAMPLE, project_url=PROJECT_URL_EXAMPLE
    )
