"""sphinx builder module."""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

import requests

from devildex.grabbers.abstract_grabber import AbstractGrabber
from devildex.info import PROJECT_ROOT
from devildex.scanner.scanner import is_sphinx_project  # Import is_sphinx_project
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command,
    install_project_and_dependencies_in_venv,
)

if TYPE_CHECKING:
    from devildex.orchestrator.context import BuildContext

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s"
    )

CONF_SPHINX_FILE = "conf.py"
REQUIREMENTS_FILENAME = "requirements.txt"


@dataclass
class RtdFinalizeConfig:
    """Configuration for finalizing the RTD build and cleanup process."""

    output_dir_param: Path | None
    existing_clone_path: str | None
    clone_base_dir_override: Path | None
    actual_clone_base_dir: Path


@dataclass
class RtdCloningConfig:
    """Configuration for repository cloning for ReadTheDocs sources."""

    repo_url: str | None
    initial_default_branch: str
    base_dir: Path
    project_slug: str
    bzr: bool


class CloneAttemptStatus(Enum):
    """Represents the status of a single clone attempt."""

    SUCCESS = auto()
    FAILED_RETRYABLE = auto()
    FAILED_CRITICAL_PREPARE_DIR = auto()
    FAILED_CRITICAL_VCS_NOT_FOUND_EXEC = auto()


@dataclass
class ProjectContext:
    """Project context."""

    slug: str
    version: str


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


class SphinxBuilder(AbstractGrabber):
    """Builder for sphinx projects."""

    def generate_docset(
        self, source_path: Path, output_path: Path, context: "BuildContext"
    ) -> str | bool:
        logger.debug(f"SphinxBuilder.generate_docset called for {context.project_slug}")
        """Generate a docset."""
        logger.info(
            "\n--- Starting Isolated Sphinx Build for %s v%s ---",
            context.project_slug,
            context.version_identifier,
        )
        source_dir_p = source_path
        clone_root_p = context.project_root_for_install
        sphinx_build_ctx = SphinxBuildContext(
            source_dir=source_dir_p,
            clone_root=clone_root_p,
            doc_requirements_file=self._find_sphinx_doc_requirements_file(
                source_dir_p, clone_root_p, context.project_slug
            ),
            project_install_root=clone_root_p,
            project_slug=context.project_slug,
            version_identifier=context.version_identifier,
            base_output_dir=output_path,
        )

        build_result: str | bool = False
        should_proceed = True

        if not sphinx_build_ctx.conf_py_file.exists():
            logger.debug(f"Critical Error: conf.py not found in {sphinx_build_ctx.source_dir}.")
            logger.error(
                "Critical Error: conf.py not found in %s.", sphinx_build_ctx.source_dir
            )
            should_proceed = False

        if should_proceed:
            logger.info(
                "Sphinx HTML output directory: %s", sphinx_build_ctx.final_output_dir
            )
            try:
                if sphinx_build_ctx.final_output_dir.exists():
                    logger.info(
                        "Removing existing output directory: %s",
                        sphinx_build_ctx.final_output_dir,
                    )
                    shutil.rmtree(sphinx_build_ctx.final_output_dir)
                sphinx_build_ctx.final_output_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                logger.exception(
                    "Error creating/cleaning output directory %s",
                    sphinx_build_ctx.final_output_dir,
                )
                should_proceed = False

        if should_proceed:
            logger.debug(f"Entering IsolatedVenvManager for {context.project_slug}")
            try:
                with IsolatedVenvManager(
                    project_name=f"{sphinx_build_ctx.project_slug}-"
                    f"{sphinx_build_ctx.version_identifier}"
                ) as venv:
                    logger.debug(f"IsolatedVenvManager entered. Venv path: {venv.venv_path}")
                    install_success = install_project_and_dependencies_in_venv(
                        pip_executable=venv.pip_executable,
                        project_name=sphinx_build_ctx.project_slug,
                        project_root_for_install=sphinx_build_ctx.project_install_root,
                        doc_requirements_path=sphinx_build_ctx.doc_requirements_file,
                        base_packages_to_install=[
                            "sphinx==7.3.7",
                            "sphinx-autoapi==1.8.4",
                            "astroid<2.12",
                            "sphinx-book-theme",
                            "sphinx-notfound-page",
                            "sphinx-copybutton",
                            "sphinx-tabs",
                            "pallets-sphinx-themes",
                            "sphinxcontrib.log-cabinet",
                        ],
                    )
                    logger.debug(f"install_project_and_dependencies_in_venv returned: {install_success}")
                    if not install_success:
                        logger.error(
                            "CRITICAL: Installation of project/dependencies"
                            " (including Sphinx) "
                            "for %s FAILED or had critical issues. "
                            "Aborting Sphinx build.",
                            sphinx_build_ctx.project_slug,
                        )
                        build_result = False
                    else:
                        sphinx_command_list = [
                            venv.python_executable,
                            "-m",
                            "sphinx",
                            "-b",
                            "html",
                            ".",
                            str(sphinx_build_ctx.final_output_dir),
                        ]
                        sphinx_process_env = {"LC_ALL": "C"}
                        logger.debug(f"Executing Sphinx command: {' '.join(sphinx_command_list)}")
                        logger.info(
                            "Executing Sphinx: %s", " ".join(sphinx_command_list)
                        )
                        stdout, stderr, return_code = execute_command(
                            sphinx_command_list,
                            f"Sphinx build for {sphinx_build_ctx.project_slug}",
                            cwd=sphinx_build_ctx.source_dir,
                            env=sphinx_process_env,
                        )
                        logger.debug(f"Sphinx command returned: return_code={return_code}, stdout={stdout}, stderr={stderr}")
                        if return_code == 0:
                            logger.info(
                                "Sphinx build for %s completed successfully.",
                                sphinx_build_ctx.project_slug,
                            )
                            build_result = str(sphinx_build_ctx.final_output_dir)
                        else:
                            logger.error(
                                "Sphinx build for %s failed. Return code: %s",
                                sphinx_build_ctx.project_slug,
                                return_code,
                            )
                            logger.error("Sphinx stdout:\n%s", stdout)
                            logger.error("Sphinx stderr:\n%s", stderr)
                            build_result = False

            except RuntimeError:
                logger.exception(
                    "Critical error during isolated build setup for %s",
                    sphinx_build_ctx.project_slug,
                )
                build_result = False
            except OSError:
                logger.exception(
                    "Error creating/cleaning output directory %s",
                    sphinx_build_ctx.final_output_dir,
                )
                build_result = False
            finally:
                logger.info(
                    "--- Finished Isolated Sphinx Build for %s ---",
                    sphinx_build_ctx.project_slug,
                )
        logger.debug(f"SphinxBuilder.generate_docset returning: {build_result}")
        return build_result
    def can_handle(self, source_path: Path, context: "BuildContext") -> bool:
        """Determine if current grabber can handle a project."""
        return is_sphinx_project(str(source_path))

    def _find_sphinx_doc_requirements_file(
        self, source_dir_path: Path, clone_root_path: Path, project_slug: str
    ) -> Path | None:
        """Find the specific requirements file for SPHINX documentation."""
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
                logger.info(
                    "Found documentation requirements file: %s", req_path_candidate
                )
                return req_path_candidate
        logger.info(
            "No specific 'requirements.txt' found for documentation in common "
            "locations for %s.",
            project_slug,
        )
        return None

    def _get_unique_branches_to_attempt(self, initial_default_branch: str) -> list[str]:
        """Generate a list of unique branch names to attempt for cloning."""
        potential_branches = [initial_default_branch, "master", "main"]
        unique_branches: list[str] = []
        for b_candidate in potential_branches:
            if b_candidate:
                stripped_candidate = b_candidate.strip()
                if stripped_candidate and stripped_candidate not in unique_branches:
                    unique_branches.append(stripped_candidate)
        return unique_branches

    def _get_vcs_executable(self, bzr: bool) -> str | None:
        """Determine the VCS executable path and logs if not found."""
        if not bzr:
            git_exe = shutil.which("git")
            if not git_exe:
                logger.error(
                    "Error: 'git' command not found. Ensure Git is"
                    " installed and in PATH."
                )
                return None
            return git_exe
        else:
            bzr_exe = shutil.which("bzr")
            if not bzr_exe:
                logger.error(
                    "Error: 'bzr' command not found. Ensure bzr is "
                    "installed and in PATH."
                )
                return None
            return bzr_exe

    def _attempt_single_branch_clone(
        self,
        repo_url: str,
        branch_to_try: str,
        clone_dir_path: Path,
        bzr: bool,
        vcs_executable_path: str,
    ) -> CloneAttemptStatus:
        """Attempt to clone a single specified branch of a repository.

        Handles directory preparation, command construction, and execution.
        """
        if clone_dir_path.exists():
            logger.info(f"Cleaning up existing clone directory: {clone_dir_path}")
            try:
                shutil.rmtree(clone_dir_path)
            except OSError:
                logger.exception(
                    f"Failed to clean up existing clone directory {clone_dir_path}."
                )
                return CloneAttemptStatus.FAILED_CRITICAL_PREPARE_DIR

        cmd_list: list[str]
        if not bzr:
            cmd_list = [
                vcs_executable_path,
                "clone",
                "--depth",
                "1",
                "--branch",
                branch_to_try,
                repo_url,
                str(clone_dir_path),
            ]
        else:
            cmd_list = [vcs_executable_path, "branch", repo_url, str(clone_dir_path)]

        try:
            logger.debug(f"Executing clone command: {' '.join(cmd_list)}")
            result = subprocess.run(  # noqa: S603
                cmd_list,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode == 0:
                return CloneAttemptStatus.SUCCESS
            else:
                logger.warning(
                    f"Failed to clone branch '{branch_to_try}'. "
                    f"Return code: {result.returncode}. "
                    f"Stdout: {result.stdout.strip()} "
                    f"Stderr: {result.stderr.strip()}"
                )
                return CloneAttemptStatus.FAILED_RETRYABLE
        except FileNotFoundError:
            logger.exception(
                f"Error: VCS command ({vcs_executable_path}) not found "
                "during subprocess.run. "
                "This indicates a critical issue with the VCS executable."
            )
            return CloneAttemptStatus.FAILED_CRITICAL_VCS_NOT_FOUND_EXEC
        except OSError:
            logger.exception(
                f"OS error during subprocess run for clone of branch {branch_to_try}"
            )
            return CloneAttemptStatus.FAILED_RETRYABLE

    def _run_clone(
        self,
        repo_url: str,
        initial_default_branch: str,
        clone_dir_path: Path,
        bzr: bool,
    ) -> str | None:
        """Perform a VCS clone, trying a list of common branches."""
        logger.info(
            "Attempting to clone repository (initial branch "
            f"'{initial_default_branch}') into: {clone_dir_path}"
        )

        unique_branches_to_attempt = self._get_unique_branches_to_attempt(
            initial_default_branch
        )
        if not unique_branches_to_attempt:
            logger.error(f"No valid branches to attempt for cloning {repo_url}.")
            return None

        vcs_executable_path = self._get_vcs_executable(bzr)
        if not vcs_executable_path:
            return None

        cloned_branch_name: str | None = None
        for branch_to_try in unique_branches_to_attempt:
            logger.info(f"Trying to clone branch: '{branch_to_try}' from {repo_url}")

            status = self._attempt_single_branch_clone(
                repo_url, branch_to_try, clone_dir_path, bzr, vcs_executable_path
            )

            if status == CloneAttemptStatus.SUCCESS:
                logger.info(
                    f"Successfully cloned branch '{branch_to_try}' "
                    f"from {repo_url} into {clone_dir_path}"
                )
                cloned_branch_name = branch_to_try
                break
            elif status == CloneAttemptStatus.FAILED_CRITICAL_PREPARE_DIR:
                logger.error(
                    "Critical error preparing clone directory. Aborting all "
                    "clone attempts for this repository."
                )
                return None
            elif status == CloneAttemptStatus.FAILED_CRITICAL_VCS_NOT_FOUND_EXEC:
                logger.error(
                    "Critical error: VCS command not found during execution. "
                    "Aborting all clone attempts for this repository."
                )
                return None

        if not cloned_branch_name:
            logger.error(
                "Failed to clone any of the attempted branches "
                f"({', '.join(unique_branches_to_attempt)}) for {repo_url}."
            )

        return cloned_branch_name

    def _find_doc_source_in_clone(self, repo_path: Path) -> str | None:
        """Identify the documentation source directory within a cloned repository.

        It does NOT copy any files.

        Args:
            repo_path (str): The local path to the cloned repository.

        Returns:
            str: The path to the documentation source directory (containing conf.py),
                 or None if not found.

        """
        logger.info(f"\nSearching for documentation source directory in: {repo_path}")
        potential_doc_dirs = ["docs", "doc", "Doc"]
        doc_source_path = self._find_doc_dir_in_repo(str(repo_path), potential_doc_dirs)
        if not doc_source_path:
            logger.error(
                "No documentation source directory with conf.py found in the clone."
            )
            return None
        logger.info(f"Documentation source directory identified at: {doc_source_path}")
        return doc_source_path

    def _find_doc_dir_in_repo(
        self, repo_path: str, potential_doc_dirs: list
    ) -> str | None:
        """Find the first potential documentation dir that contains a conf.py file.

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
                logger.info(
                    "Found documentation source directory with conf.py: "
                    f"{current_path}"
                )
                return current_path
            if os.path.isdir(current_path):
                logger.warning(
                    f"Found directory '{current_path}', but no conf.py. "
                    "Continuing search..."
                )
        if os.path.exists(os.path.join(repo_path, CONF_SPHINX_FILE)):
            logger.info(f"Found conf.py in the repository root: {repo_path}")
            return repo_path

        logger.info(
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
                logger.info(
                    "Found conf.py via full recursive search at: "
                    f"{conf_file_path} (source directory: {doc_source_dir})"
                )
                return doc_source_dir
        return None

    def _cleanup(self, clone_dir_path: Path | None) -> None:
        if clone_dir_path and clone_dir_path.exists():
            logger.info(f"\nDeleting repository cloned directory: {clone_dir_path}")
            try:
                shutil.rmtree(clone_dir_path)
                logger.info("Delete completed.")
            except OSError:
                logger.exception(
                    "Error during deleting della repository cloned "
                    f"'{clone_dir_path}'"
                )

    def _extract_repo_url_branch(
        self, api_project_detail_url: str, project_slug: str
    ) -> tuple[str, str | None]:
        repo_url: str | None = None
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
                logger.error(
                    "Warning: URL del repository sources non trovato per "
                    f"'{project_slug}' using API."
                )
            else:
                logger.info(f"Trovato URL repository: {repo_url}")
                logger.info(
                    "Branch di default (used come version identifier): "
                    f"{default_branch}"
                )
        except requests.exceptions.RequestException:
            logger.exception("Warning: Error durante la richiesta API: ")
            logger.exception(
                "Provo a search la repository cloned locally if already exists."
            )
        return default_branch, repo_url

    def _attempt_clone_and_process_result(
        self,
        repo_url: str,
        initial_default_branch: str,
        clone_dir_path: Path,
        bzr: bool,
        project_slug: str,
    ) -> tuple[bool, str]:
        """Clone the repository and process the result."""
        branch_actually_cloned = self._run_clone(
            repo_url, initial_default_branch, clone_dir_path, bzr
        )

        if branch_actually_cloned:
            logger.info(
                "Cloning successful for '%s'. Effective branch: '%s'. Path: '%s'",
                project_slug,
                branch_actually_cloned,
                clone_dir_path,
            )
            return True, branch_actually_cloned
        else:
            logger.error(
                "Cloning failed for '%s' (details in previous logs). "
                "Will use initial default branch ('%s') for context, "
                "but build may fail or use wrong version.",
                project_slug,
                initial_default_branch,
            )
            return False, initial_default_branch

    def _handle_repository_cloning(
        self, config: RtdCloningConfig
    ) -> tuple[Path | None, str]:
        """Manage the cloning logic of the repository.

        Returns the path of the clone and the actual branch used.
        """
        clone_dir_name = f"{config.project_slug}_repo_{config.initial_default_branch}"
        clone_dir_path = config.base_dir / clone_dir_name
        effective_branch = config.initial_default_branch
        cloned_repo_exists_before = clone_dir_path.exists()
        if config.repo_url and not cloned_repo_exists_before:
            logger.info(
                "Repository for '%s' not found locally at '%s'. Attempting to clone.",
                config.project_slug,
                clone_dir_path,
            )
            _, branch_after_attempt = self._attempt_clone_and_process_result(
                config.repo_url,
                config.initial_default_branch,
                clone_dir_path,
                config.bzr,
                config.project_slug,
            )
            effective_branch = branch_after_attempt
        elif config.repo_url and cloned_repo_exists_before:
            logger.info(
                "Repository for '%s' already exists at '%s'. Skipping clone.",
                config.project_slug,
                clone_dir_path,
            )
        elif not config.repo_url:
            logger.warning(
                "No repository URL provided for '%s'. Cannot clone.",
                config.project_slug,
            )
            if not cloned_repo_exists_before:
                logger.error(
                    "No repository URL and no existing clone for '%s'.",
                    config.project_slug,
                )
                return None, effective_branch
        if clone_dir_path.exists():
            logger.info(
                "Using repository for '%s' at: '%s'",
                config.project_slug,
                clone_dir_path,
            )
            return clone_dir_path, effective_branch
        logger.error(
            "Repository directory for '%s' not found at '%s' after processing.",
            config.project_slug,
            clone_dir_path,
        )
        return None, effective_branch

    def _process_documentation(
        self,
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
        isolated_source_path = self._find_doc_source_in_clone(clone_dir_path)
        build_output_path = None
        if isolated_source_path:
            logger.info(
                "Documentation source for '%s' isolated at: %s",
                project_ctx.slug,
                isolated_source_path,
            )
        else:
            logger.warning(
                "Documentation source isolation failed for '%s' (path: '%s'). "
                "Skipping Sphinx build.",
                project_ctx.slug,
                clone_dir_path,
            )
        return isolated_source_path, build_output_path

    def _prepare_rtd_build_environment(
        self, project_name: str, clone_base_dir_override: Path | None
    ) -> tuple[str | None, str | None, str | None, Path | None, bool]:
        """Prepare environment for RTD build: validate slug, get repo details."""
        project_slug = project_name
        if not project_slug:
            logger.error("Project slug (project_name) cannot be empty.")
            return None, None, None, None, False

        logger.info("Project Slug: %s", project_slug)
        api_project_detail_url = (
            f"https://readthedocs.org/api/v3/projects/{project_slug}/"
        )
        logger.info("Fetching project details from API: %s", api_project_detail_url)

        initial_default_branch, repo_url = self._extract_repo_url_branch(
            api_project_detail_url, project_slug
        )

        actual_clone_base_dir: Path
        if clone_base_dir_override:
            actual_clone_base_dir = clone_base_dir_override
        else:
            actual_clone_base_dir = PROJECT_ROOT / "rtd_source_clones_temp"
        actual_clone_base_dir.mkdir(parents=True, exist_ok=True)

        bzr = bool(repo_url and repo_url.startswith("lp:"))
        return (
            project_slug,
            initial_default_branch,
            repo_url,
            actual_clone_base_dir,
            bzr,
        )

    def _obtain_rtd_source_code(
        self,
        existing_clone_path: str | None,
        cloning_config: RtdCloningConfig,
    ) -> tuple[Path | None, str]:
        """Obtain the source code, either from existing path or by cloning."""
        clone_dir_path: Path | None
        effective_branch: str = cloning_config.initial_default_branch

        if existing_clone_path:
            existing_clone_path_obj = Path(existing_clone_path)
            if existing_clone_path_obj.exists() and existing_clone_path_obj.is_dir():
                logger.info("Using existing clone path: %s", existing_clone_path)
                clone_dir_path = existing_clone_path_obj
            else:
                logger.warning(
                    f"Provided existing_clone_path '{existing_clone_path}'"
                    " not found or not a dir. Attempting clone."
                )
                clone_dir_path, effective_branch = self._handle_repository_cloning(
                    cloning_config
                )
        else:
            clone_dir_path, effective_branch = self._handle_repository_cloning(
                cloning_config
            )
        return clone_dir_path, effective_branch

    def download_and_prepare_rtd_source(
        self,
        project_name: str,
        project_url: str,
        existing_clone_path: str | None = None,
        output_dir: Path | None = None,
        clone_base_dir_override: Path | None = None,
    ) -> str | bool:
        """Download sources from RTD, clones, isolates doc sources, execute Sphinx."""
        logger.info(
            "\n--- Starting RTD Source Download, Build & Cleanup for: %s ---",
            project_name,
        )
        logger.info("Project URL: %s", project_url)

        (
            project_slug,
            initial_default_branch,
            repo_url_from_api,
            actual_clone_base_dir,
            bzr,
        ) = self._prepare_rtd_build_environment(project_name, clone_base_dir_override)

        if not project_slug or not actual_clone_base_dir:
            return False
        cloning_conf = RtdCloningConfig(
            repo_url=repo_url_from_api,
            initial_default_branch=initial_default_branch,
            base_dir=actual_clone_base_dir,
            project_slug=project_slug,
            bzr=bzr,
        )
        clone_dir_path, effective_branch = self._obtain_rtd_source_code(
            existing_clone_path, cloning_conf
        )

        if not clone_dir_path:
            logger.error(
                "Failed to obtain a valid repository clone for '%s'.", project_slug
            )
            if (
                not clone_base_dir_override
                and actual_clone_base_dir.exists()
                and not any(actual_clone_base_dir.iterdir())
            ):
                self._cleanup(actual_clone_base_dir)
            return False

        project_context = ProjectContext(slug=project_slug, version=effective_branch)
        finalize_conf = RtdFinalizeConfig(
            output_dir_param=output_dir,
            existing_clone_path=existing_clone_path,
            clone_base_dir_override=clone_base_dir_override,
            actual_clone_base_dir=actual_clone_base_dir,
        )
        return self._finalize_rtd_source_preparation_and_cleanup(
            clone_dir_path,
            project_context,
            finalize_conf,
        )

    def _finalize_rtd_source_preparation_and_cleanup(
        self,
        clone_dir_path: Path,
        project_context: ProjectContext,
        config: RtdFinalizeConfig,
    ) -> str | bool:
        """Process documentation, cleanup, and return result."""
        isolated_source_path_str, _ = self._process_documentation(
            clone_dir_path,
            project_context,
            base_output_dir=None,
        )

        if not config.existing_clone_path:
            self._cleanup(clone_dir_path)
            if (
                not config.clone_base_dir_override
                and config.actual_clone_base_dir.exists()
                and not any(config.actual_clone_base_dir.iterdir())
            ):
                logger.info(
                    "Cleaning up empty base clone directory: "
                    f"{config.actual_clone_base_dir}"
                )
                self._cleanup(config.actual_clone_base_dir)
        elif config.existing_clone_path:
            logger.info(
                "Skipping cleanup for pre-existing clone path: %s",
                config.existing_clone_path,
            )

        return isolated_source_path_str if isolated_source_path_str else False
