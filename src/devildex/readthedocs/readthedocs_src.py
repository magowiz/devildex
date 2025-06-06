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
GIT_FULL_PATH = shutil.which("git")


def find_doc_source_in_clone(repo_path: Path) -> str | None:
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
    doc_source_path = _find_doc_dir_in_repo(str(repo_path), potential_doc_dirs)
    if not doc_source_path:
        logger.error("No documentation source directory with conf.py "
                     "found in the clone.")
        return None
    logger.info(f"Documentation source directory identified at: {doc_source_path}")
    return doc_source_path


def _find_doc_dir_in_repo(repo_path: str, potential_doc_dirs: list) -> str | None:
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
            logger.info(
                "Found documentation source directory with conf.py: " f"{current_path}"
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
    except OSError:
        logger.exception(
            "Error creating/cleaning output directory %s", sctx.final_output_dir
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

    except RuntimeError:
        logger.exception(
            "Critical error during isolated build setup for %s",
            sctx.project_slug
        )
    except OSError:
        logger.exception(
            "Error creating/cleaning output directory %s", sctx.final_output_dir
        )
        return None
    finally:
        logger.info("--- Finished Isolated Sphinx Build for %s ---", sctx.project_slug)
    return str(sctx.final_output_dir) if build_successful else None


def _cleanup(clone_dir_path: Path | None) -> None:
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
    api_project_detail_url: str, project_slug: str
) -> tuple[str, str| None]:
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
            logger.info("Branch di default (used come version identifier): "
                        f"{default_branch}")
    except requests.exceptions.RequestException:
        logger.exception("Warning: Error durante la richiesta API: ")
        logger.exception("Provo a search la repository cloned locally "
                         "if already exists.")
    return default_branch, repo_url


# ... (codice precedente di _extract_repo_url_branch) ...

def run_clone(
    repo_url: str, initial_default_branch: str, clone_dir_path: Path, bzr: bool # Rinominato default_branch
) -> str | None: # MODIFICATO: firma di ritorno più semplice
    """Perform a clone for matching vcs. Tries initial_default_branch then fallbacks."""
    logger.info(
        f"Attempting to clone repository (initial branch '{initial_default_branch}') into: {clone_dir_path}"
    )

    branches_to_attempt = [initial_default_branch, "master", "main"]
    # Filtra None/stringhe vuote e rimuovi duplicati, mantenendo l'ordine
    unique_branches_to_attempt = []
    for b_candidate in branches_to_attempt:
        if b_candidate and b_candidate.strip() and b_candidate.strip() not in unique_branches_to_attempt:
            unique_branches_to_attempt.append(b_candidate.strip())

    if not unique_branches_to_attempt:
        logger.error(f"No valid branches to attempt for cloning {repo_url}.")
        return None

    vcs_command_path: str | None
    if not bzr:
        vcs_command_path = GIT_FULL_PATH
        if not vcs_command_path:
            logger.error("Error: 'git' command not found. Ensure Git is installed and in PATH.")
            return None
    else: # bzr
        vcs_command_path = shutil.which("bzr")
        if not vcs_command_path:
            logger.error("Error: 'bzr' command not found.")
            return None

    for branch_to_try in unique_branches_to_attempt:
        logger.info(f"Trying to clone branch: {branch_to_try} from {repo_url}")

        if clone_dir_path.exists():
            logger.info(f"Cleaning up existing clone directory: {clone_dir_path}")
            try:
                shutil.rmtree(clone_dir_path)
            except OSError as e_rm:
                logger.exception(f"Failed to clean up {clone_dir_path}: {e_rm}")
                return None

        cmd_list: list[str] = []
        if not bzr:
            if not vcs_command_path: logger.error("GIT_FULL_PATH is None, cannot clone."); return None
            cmd_list = [
                vcs_command_path, "clone", "--depth", "1", "--branch", branch_to_try,
                repo_url, str(clone_dir_path),
            ]
        else: # bzr
            if not vcs_command_path: logger.error("bzr path is None, cannot clone."); return None
            cmd_list = [vcs_command_path, "branch", repo_url, str(clone_dir_path)]

        try:
            logger.debug(f"Executing clone command: {' '.join(cmd_list)}")
            result = subprocess.run(
                cmd_list,
                check=False, # Controlliamo il returncode manualmente
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode == 0:
                logger.info(
                    f"Successfully cloned branch '{branch_to_try}' "
                    f"from {repo_url} into {clone_dir_path}"
                )
                return branch_to_try # SUCCESSO: restituisce il nome del branch clonato
            else:
                logger.warning(
                    f"Failed to clone branch '{branch_to_try}'. "
                    f"Return code: {result.returncode}. Stdout: {result.stdout.strip()} Stderr: {result.stderr.strip()}"
                )
        except FileNotFoundError: # Se il comando VCS non viene trovato durante subprocess.run
            logger.exception(f"Error: VCS command ({vcs_command_path}) not found during subprocess.run.")
            return None # Fallimento critico
        except Exception as e_subproc: # Altri errori imprevisti da subprocess
            logger.exception(f"Unexpected error during subprocess run for clone of branch {branch_to_try}: {e_subproc}")
            # Continua con il prossimo tentativo di branch se questo fallisce per un'eccezione imprevista

    logger.error(f"Failed to clone any of the attempted branches for {repo_url}.")
    return None # Tutti i tentativi sono falliti





# ... (codice precedente di run_clone) ...

def _attempt_clone_and_process_result(
    repo_url: str,
    initial_default_branch: str, # Branch suggerito dall'API o default
    clone_dir_path: Path,
    bzr: bool,
    project_slug: str,
) -> tuple[bool, str]:
    """Tenta di clonare il repository e processa il risultato."""
    branch_actually_cloned = run_clone(repo_url, initial_default_branch, clone_dir_path, bzr)

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
            initial_default_branch
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
    isolated_source_path = find_doc_source_in_clone(clone_dir_path)
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
    output_dir: Path | None = None, # Questa è la base_output_dir dell'Orchestrator
    clone_base_dir_override: Path | None = None,
) -> str | bool: # MODIFICATO: tipo di ritorno per i test
    """Scarica sorgenti da RTD, clona, isola sorgenti doc, esegue Sphinx e pulisce."""
    logger.info(
        "\n--- Starting RTD Source Download, Build & Cleanup for: %s ---", project_name
    )
    logger.info("Project URL: %s", project_url)

    project_slug = project_name
    if not project_slug:
        logger.error("Project slug (project_name) cannot be empty.")
        return False # MODIFICATO: ritorno per fallimento

    logger.info("Project Slug: %s", project_slug)
    # Semplificazione: assumiamo che project_url sia l'URL API o che _extract_repo_url_branch lo gestisca
    # In uno scenario reale, potresti voler distinguere meglio gli URL RTD dagli URL VCS diretti
    api_project_detail_url = f"https://readthedocs.org/api/v3/projects/{project_slug}/"
    # Se project_url è già un URL VCS, questa chiamata a _extract_repo_url_branch potrebbe fallire
    # o restituire valori non ottimali. Per ora, manteniamo la logica esistente.
    logger.info("Fetching project details from API: %s", api_project_detail_url)

    initial_default_branch, repo_url = _extract_repo_url_branch(
        api_project_detail_url, project_slug
    )

    # Determina la directory base per i cloni
    actual_clone_base_dir: Path
    if clone_base_dir_override:
        actual_clone_base_dir = clone_base_dir_override
    else:
        actual_clone_base_dir = PROJECT_ROOT / "rtd_source_clones_temp" # O un percorso temporaneo migliore
    actual_clone_base_dir.mkdir(parents=True, exist_ok=True)

    bzr = bool(repo_url and repo_url.startswith("lp:")) # repo_url può essere None qui
    clone_dir_path: Path | None # Può essere None se _handle_repository_cloning fallisce
    effective_branch: str

    if existing_clone_path:
        existing_clone_path_obj = Path(existing_clone_path)
        if existing_clone_path_obj.exists() and existing_clone_path_obj.is_dir():
            logger.info("Using existing clone path: %s", existing_clone_path)
            clone_dir_path = existing_clone_path_obj
            effective_branch = initial_default_branch # O cerca di determinarlo dal clone
        else:
            logger.warning(f"Provided existing_clone_path '{existing_clone_path}' not found or not a dir. Attempting clone.")
            # Se il percorso esistente non è valido, procedi con la clonazione normale
            clone_dir_path, effective_branch = _handle_repository_cloning(
                repo_url, initial_default_branch, actual_clone_base_dir, project_slug, bzr
            )
    else:
        clone_dir_path, effective_branch = _handle_repository_cloning(
            repo_url, initial_default_branch, actual_clone_base_dir, project_slug, bzr
        )

    if not clone_dir_path: # Se _handle_repository_cloning restituisce None per il percorso
        logger.error(
            "Failed to obtain a valid repository clone for '%s'.", project_slug
        )
        # Opzionale: pulisci actual_clone_base_dir se è vuota e creata da noi
        if not clone_base_dir_override and actual_clone_base_dir.exists() and not any(actual_clone_base_dir.iterdir()):
            _cleanup(actual_clone_base_dir)
        return False # MODIFICATO: ritorno per fallimento

    project_context = ProjectContext(slug=project_slug, version=effective_branch)

    # Determina la directory di output finale per la build Sphinx
    final_sphinx_build_destination: Path
    if output_dir: # Questa è la base_output_dir dell'Orchestrator
        final_sphinx_build_destination = output_dir
    else: # Fallback se non fornita (non dovrebbe accadere se chiamato dall'Orchestrator)
        final_sphinx_build_destination = (
            PROJECT_ROOT / "devildex_sphinx_build_output_default"
        )
        logger.warning(f"output_dir not provided, using fallback: {final_sphinx_build_destination}")
    final_sphinx_build_destination.mkdir(parents=True, exist_ok=True)


    isolated_source_path_str, built_docs_path_str = _process_documentation(
        clone_dir_path,
        project_context,
        base_output_dir=final_sphinx_build_destination, # Passa la directory base corretta
    )

    if not existing_clone_path:
        _cleanup(clone_dir_path) # _cleanup accetta Path | None
        # Opzionale: pulisci actual_clone_base_dir se è vuota dopo aver pulito il clone specifico
        if not clone_base_dir_override and actual_clone_base_dir.exists() and not any(actual_clone_base_dir.iterdir()):
            logger.info(f"Cleaning up empty base clone directory: {actual_clone_base_dir}")
            _cleanup(actual_clone_base_dir)
    elif existing_clone_path:
        logger.info("Skipping cleanup for pre-existing clone path: %s", existing_clone_path)


    final_result_path_str = _download_handle_result(
        isolated_source_path_str,
        built_docs_path_str
    )

    if final_result_path_str:
        return final_result_path_str
    else:
        return False

def _download_handle_result(
    isolated_source_path_str: str | None,
    built_docs_path_str: str | None
) -> str | None:
    """Determina il risultato finale del processo di build della documentazione.

    Args:
        isolated_source_path_str: Percorso sorgente isolato (str o None).
        built_docs_path_str: Percorso della documentazione buildata (str o None).

    Returns:
        La stringa del percorso assoluto della documentazione buildata con successo,
        o None se la build è fallita o i percorsi essenziali mancavano.

    """
    if built_docs_path_str: # La build ha avuto successo e ha prodotto un percorso di output
        # built_docs_path_str è già una stringa, Path() è corretto per risolverlo
        final_built_path = Path(built_docs_path_str).resolve()
        logger.info(f"\nBuild HTML Sphinx generata in:    {final_built_path}")
        if isolated_source_path_str: # Logga anche il percorso sorgente se disponibile
            logger.info(f"Sorgente isolata della documentazione era in: {isolated_source_path_str}")
        return str(final_built_path) # Successo, restituisce la stringa del percorso

    # Se built_docs_path_str è None, la build è fallita
    logger.error("Build Sphinx fallita.")
    if isolated_source_path_str:
        logger.info(f"Sorgente isolata della documentazione era in: {isolated_source_path_str}, ma la build è fallita.")
    else:
        logger.error("Anche l'isolamento della sorgente è fallito.")
    return None # Fallimento


if __name__ == "__main__":
    PROJECT_NAME_EXAMPLE = "black"
    PROJECT_URL_EXAMPLE = "https://github.com/psf/black"
    _, _ = download_readthedocs_source_and_build(
        project_name=PROJECT_NAME_EXAMPLE, project_url=PROJECT_URL_EXAMPLE
    )
