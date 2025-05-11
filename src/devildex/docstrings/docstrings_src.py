"""docstrings pdoc3 module."""

import importlib
import logging
import os
import re
import shutil
import subprocess
import sys
import traceback
import venv
from pathlib import Path
from types import ModuleType

import pdoc
logger = logging.getLogger(__name__)
CONFIG_FILE = "../../../devildex_config.ini"


class DocStringsSrc:
    def __init__(self):
        """Initialize il DocStringsSrc."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.docset_dir = project_root / "docset"
        self.docset_dir.mkdir(parents=True, exist_ok=True)

    def _try_process_module(
        self,
        module_name_to_process: str,
        context: pdoc.Context,
        venv_python_interpreter: str | None,
    ) -> list[pdoc.Module]:
        processed_pdoc_modules: list[pdoc.Module] = []
        module_obj: ModuleType | None = None
        pdoc_module_instance: pdoc.Module | None = None

        for attempt in range(2):
            try:
                current_module_obj_candidate = pdoc.import_module(
                    module_name_to_process, reload=True, skip_errors=True
                )

                is_dummy = (
                    not hasattr(current_module_obj_candidate, "__file__")
                    and not hasattr(current_module_obj_candidate, "__path__")
                    and (
                        not hasattr(current_module_obj_candidate, "__name__")
                        or current_module_obj_candidate.__name__
                        != module_name_to_process
                    )
                )

                if is_dummy:
                    if attempt == 0 and venv_python_interpreter:
                        raise ModuleNotFoundError(
                            f"No module named '{module_name_to_process}' "
                            "(pdoc returned dummy object)"
                        )
                    else:
                        module_obj = None
                        break

                module_obj = current_module_obj_candidate
                pdoc_module_instance = pdoc.Module(module_obj, context=context)
                break

            except (ModuleNotFoundError, ImportError) as import_err:
                module_obj = None
                pdoc_module_instance = None
                if attempt == 0 and venv_python_interpreter:
                    missing_module_name = self._extract_missing_module_name(
                        str(import_err)
                    )
                    if (
                        missing_module_name
                        and missing_module_name.strip()
                        and missing_module_name != module_name_to_process
                    ):
                        try:
                            pip_install_cmd = [
                                str(venv_python_interpreter),
                                "-m",
                                "pip",
                                "install",
                                missing_module_name,
                            ]
                            install_result = subprocess.run(
                                pip_install_cmd,
                                check=False,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                            )
                            if install_result.returncode == 0:
                                print(
                                    f"Installation of '{missing_module_name}' "
                                    f"completed. "
                                    f"Retrying importing of "
                                    f"'{module_name_to_process}'."
                                )
                                if missing_module_name in sys.modules:
                                    del sys.modules[missing_module_name]
                                importlib.invalidate_caches()
                            else:
                                print(
                                    "ERROR: Failed installation of "
                                    f"'{missing_module_name}':"
                                )
                                print(f"  Stdout: {install_result.stdout.strip()}")
                                print(f"  Stderr: {install_result.stderr.strip()}")
                                break
                        except Exception as pip_exec_err:
                            print(
                                "ERROR: Exception during try to install "
                                f"'{missing_module_name}': {pip_exec_err}"
                            )
                            break
                    else:
                        break
                else:
                    break
            except Exception:
                pdoc_module_instance = None
                break

        if pdoc_module_instance and module_obj:
            processed_pdoc_modules.append(pdoc_module_instance)
            print(
                f"INFO: main Modulo '{module_name_to_process}' "
                "successfully wrapped."
            )
        elif (
            module_obj
            and isinstance(module_obj, ModuleType)
            and hasattr(module_obj, "__path__")
        ):
            print(
                f"INFO: main Module '{module_name_to_process}' not wrapped. "
                "Try to recover submodules..."
            )
            found_salvageable_submodule = False
            for submodule_info in pdoc.iter_submodules(module_obj):
                submodule_qualname = submodule_info.name
                try:
                    submodule_actual_obj = pdoc.import_module(
                        submodule_qualname, reload=True, skip_errors=False
                    )
                    if not submodule_actual_obj:
                        continue
                    sub_pdoc_instance = pdoc.Module(
                        submodule_actual_obj, context=context
                    )
                    processed_pdoc_modules.append(sub_pdoc_instance)
                    print(
                        "  SUCCESS: Recovered and wrapped submodule "
                        f"'{submodule_qualname}'."
                    )
                    found_salvageable_submodule = True
                except ImportError as sub_import_err:
                    print(
                        "  FAILED IMPORT (submodule): unable to import "
                        f"'{submodule_qualname}': {sub_import_err}"
                    )
                except Exception as sub_wrap_err:
                    print(
                        "  FAILED WRAP (submodule): Error durante il wrapping di "
                        f"'{submodule_qualname}': {sub_wrap_err.__class__.__name__}: "
                        f"{sub_wrap_err}"
                    )
            if not found_salvageable_submodule:
                print(
                    f"INFO: No submodule di '{module_name_to_process}' "
                    "successfully recovered."
                )
        elif module_obj:
            print(
                f"INFO: Modulo '{module_name_to_process}' imported ma non wrapped e "
                f"non è un package. No submodule to recover."
            )
        else:
            print(
                f"INFO: Modulo '{module_name_to_process}' not imported. "
                "No submodule to recover."
            )
        return processed_pdoc_modules

    def get_docset_dir(self):
        return self.docset_dir

    def _discover_modules_in_folder(self, input_folder_path: Path) -> list[str]:
        """Discover Python modules and packages di first level in una data folder."""
        discovered_names = []
        for item_name in os.listdir(input_folder_path):
            item_path = input_folder_path / item_name
            if item_name.startswith((".", "__")):
                continue

            if item_path.is_file() and item_name.endswith(".py"):
                module_name = item_name[:-3]
                if module_name == "__init__":
                    continue
                discovered_names.append(module_name)
            elif item_path.is_dir():
                if (item_path / "__init__.py").exists():
                    package_name = item_name
                    discovered_names.append(package_name)
        return discovered_names

    def generate_docs_from_folder(
            self,
            project_name: str,  # Nome del progetto/modulo principale da documentare (es. "fastapi")
            input_folder: str,  # Path alla radice del clone del progetto (es. "/tmp/clone_di_fastapi")
            output_folder: str,
            # Path alla directory base dove TUTTI i docset pdoc vengono salvati (es. "PROJECT_ROOT/docset")
            # Questo 'output_folder' è self.pdoc_base_output_dir
            # L'argomento 'modules_to_document' non è più necessario se documentiamo 'project_name'.
            # L'argomento 'venv_python_interpreter' non è più necessario.
    ) -> str | bool:  # Restituisce il percorso alla documentazione specifica del progetto (es. "docset/fastapi") o False
        """
        Genera documentazione HTML per un progetto Python usando pdoc in un ambiente isolato.
        """
        source_project_path = Path(input_folder)  # Radice del clone del progetto
        # output_folder passato dall'Orchestrator è già la base, es. "PROJECT_ROOT/docset"
        # quindi base_output_dir_for_pdoc è output_folder.
        base_output_dir_for_pdoc = Path(output_folder)

        final_project_pdoc_output_dir = base_output_dir_for_pdoc / project_name

        logger.info(f"--- Starting Isolated pdoc Build for {project_name} ---")
        logger.info(f"DocStringsSrc: Project root (cloned input): {source_project_path}")
        logger.info(f"DocStringsSrc: Module to document with pdoc: {project_name}")
        logger.info(f"DocStringsSrc: Base output directory for pdoc outputs: {base_output_dir_for_pdoc}")
        logger.info(f"DocStringsSrc: Final output directory for this project: {final_project_pdoc_output_dir}")

        # 1. Pulizia della directory di output specifica per questo progetto, se esiste
        if final_project_pdoc_output_dir.exists():
            logger.info(f"DocStringsSrc: Removing existing pdoc output directory: {final_project_pdoc_output_dir}")
            try:
                shutil.rmtree(final_project_pdoc_output_dir)
            except OSError as e:
                logger.error(f"DocStringsSrc: Error removing {final_project_pdoc_output_dir}: {e}")
                return False  # Non possiamo procedere se non possiamo pulire

        # Non creiamo final_project_pdoc_output_dir qui, pdoc lo farà.
        # Assicuriamoci che la directory base (base_output_dir_for_pdoc) esista.
        base_output_dir_for_pdoc.mkdir(parents=True, exist_ok=True)

        # 2. Trova un file requirements.txt (opzionale) nella radice del progetto clonato
        requirements_file_to_install: Path | None = None
        candidate_req_paths = [
            source_project_path / "requirements.txt",
            source_project_path / "dev-requirements.txt",  # Alcuni progetti usano questo
            source_project_path / "requirements-dev.txt",
            # Aggiungi altri percorsi candidati se il progetto ha requirements specifici per i docs
            # in posti non standard, ma per pdoc, i requirements generali del progetto sono più importanti.
            source_project_path / "docs" / "requirements.txt",  # Meno probabile per pdoc, più per Sphinx
        ]
        for req_path_candidate in candidate_req_paths:
            if req_path_candidate.exists() and req_path_candidate.is_file():
                requirements_file_to_install = req_path_candidate
                logger.info(f"DocStringsSrc: Found requirements file for dependencies: {requirements_file_to_install}")
                break
        if not requirements_file_to_install:
            logger.info(f"DocStringsSrc: No general 'requirements.txt' found for {project_name} in common locations. "
                        "Will rely on project's setup (e.g., setup.py, pyproject.toml).")

        build_successful = False
        try:
            # 3. Usa IsolatedVenvManager
            with IsolatedVenvManager(project_name=f"pdoc_{project_name}") as venv:
                logger.info(f"DocStringsSrc: Created temporary venv for pdoc at {venv.venv_path}")

                # 4. Installa pdoc e le dipendenze del progetto nel venv
                install_deps_success = install_project_and_dependencies_in_venv(
                    pip_executable=venv.pip_executable,
                    project_name=project_name,
                    project_root_for_install=source_project_path,  # Per `pip install -e .`
                    doc_requirements_path=requirements_file_to_install,
                    base_packages_to_install=["pdoc>=14.0"]  # Installa pdoc nel venv
                )

                if not install_deps_success:
                    # install_project_and_dependencies_in_venv restituisce False
                    # solo se l'installazione dei pacchetti base (pdoc qui) fallisce.
                    logger.error(f"DocStringsSrc: CRITICAL: Failed to install pdoc "
                                 f"for {project_name} in venv. Aborting pdoc build.")
                    return False  # Fallimento critico

                # 5. Esegui pdoc usando execute_command
                # Comando: python -m pdoc <module_name> --html -o <output_base_dir>
                # pdoc creerà <output_base_dir>/<module_name>/index.html
                pdoc_command = [
                    venv.python_executable,  # Python del venv
                    "-m", "pdoc",
                    project_name,  # Il modulo/package principale da documentare
                    "--html",  # Forza output HTML
                    "-o", str(base_output_dir_for_pdoc.resolve())  # Directory base per l'output di pdoc
                ]

                logger.info(f"DocStringsSrc: Executing pdoc: {' '.join(pdoc_command)}")
                # Esegui pdoc dalla radice del progetto clonato (input_folder)
                # così che pdoc possa risolvere import relativi se il progetto li usa.
                stdout, stderr, returncode = execute_command(
                    pdoc_command,
                    f"pdoc HTML generation for {project_name}",
                    cwd=source_project_path  # Esegui dalla radice del progetto clonato
                )

                if returncode == 0:
                    # Verifica che l'output atteso (es. docset/fastapi/index.html) sia stato creato
                    if final_project_pdoc_output_dir.exists() and \
                            (final_project_pdoc_output_dir / "index.html").exists():
                        logger.info(f"DocStringsSrc: pdoc build for {project_name} completed successfully. "
                                    f"Output: {final_project_pdoc_output_dir}")
                        build_successful = True
                    else:
                        logger.error(f"DocStringsSrc: pdoc command for {project_name} seemed to succeed (exit 0) "
                                     "but expected output directory/file not found at "
                                     f"{final_project_pdoc_output_dir / 'index.html'}.")
                        logger.debug(f"pdoc stdout:\n{stdout}")
                        logger.debug(f"pdoc stderr:\n{stderr}")
                        # build_successful rimane False
                else:
                    logger.error(f"DocStringsSrc: pdoc build for {project_name} FAILED. Return code: {returncode}")
                    logger.debug(f"pdoc stdout:\n{stdout}")  # Logga sempre stdout/stderr per il debug di pdoc
                    logger.debug(f"pdoc stderr:\n{stderr}")
                    # build_successful rimane False

        except RuntimeError as e:  # Errore dalla creazione del venv
            logger.error(f"DocStringsSrc: Critical error during isolated pdoc build setup for {project_name}: {e}")
            # build_successful rimane False
        except Exception as e:  # Altre eccezioni impreviste
            logger.exception(f"DocStringsSrc: Unexpected exception during isolated pdoc build for {project_name}")
            # build_successful rimane False
        finally:
            logger.info(f"--- Finished Isolated pdoc Build for {project_name} ---")

        if build_successful:
            # Restituisce il percorso alla directory specifica del progetto (es. "docset/fastapi")
            return str(final_project_pdoc_output_dir)
        else:
            # Se la build fallisce, assicurati che la directory di output parziale venga rimossa
            if final_project_pdoc_output_dir.exists():
                logger.info(
                    f"DocStringsSrc: Cleaning up partially created/failed pdoc output at {final_project_pdoc_output_dir}")
                try:
                    shutil.rmtree(final_project_pdoc_output_dir)
                except OSError as e_clean:
                    logger.error(
                        f"DocStringsSrc: Error cleaning up failed pdoc output directory {final_project_pdoc_output_dir}: {e_clean}")
            return False
    def cleanup_folder(self, folder_or_list: Path | str | list[Path | str]):
        """Clean una single folder/file o una lista di folders/files.

        Handles sia strings che objects pathlib.Path.
        """
        items_to_clean = []
        if isinstance(folder_or_list, list):
            items_to_clean.extend(folder_or_list)
        else:
            items_to_clean.append(folder_or_list)

        for item in items_to_clean:
            item_path = Path(item)
            if not item_path.exists():
                continue

            if item_path.is_dir():
                shutil.rmtree(item_path, ignore_errors=True)
            elif item_path.is_file():
                try:
                    item_path.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass

    def git_clone(self, repo_url, clone_dir_path, default_branch="master"):
        """Clone a git repository."""
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    default_branch,
                    repo_url,
                    clone_dir_path,
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except Exception:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    "main",
                    repo_url,
                    clone_dir_path,
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

    def _extract_missing_module_name(self, error_message: str) -> str | None:
        """Extract il nome del modulo da un messaggio di ModuleNotFoundError.

        Es. "No module named 'X'" -> "X"
        """
        match = re.search(r"No module named '([^']*)'", error_message)
        if match:
            return match.group(1)
        return None

    def run(self, url, project_name, version=""):
        """Run logic."""
        cloned_repo_path: Path | None = None
        temp_venv_path: Path | None = None
        try:
            cloned_repo_path = Path(project_name)
            temp_venv_path = cloned_repo_path / ".venv_docs"

            final_output_dir = self.docset_dir / project_name / version
            tmp_output_dir = self.docset_dir / f"tmp_{project_name}" / version

            self.cleanup_folder(
                [cloned_repo_path, temp_venv_path, final_output_dir, tmp_output_dir]
            )

            self.git_clone(url, cloned_repo_path)

            venv.create(temp_venv_path, with_pip=True, clear=True)

            if sys.platform == "win32":
                _venv_python_rel = temp_venv_path / "Scripts" / "python.exe"
            else:
                _venv_python_rel = temp_venv_path / "bin" / "python"
            venv_python_interpreter = str(_venv_python_rel.resolve())

            get_site_packages_command = [
                venv_python_interpreter,
                "-c",
                "import site; print(site.getsitepackages()[0])",
            ]
            result = subprocess.run(
                get_site_packages_command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            venv_site_packages = result.stdout.strip()
            subprocess.run(
                [venv_python_interpreter, "-m", "pip", "install", "."],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=cloned_repo_path,
            )

            subprocess.run(
                [venv_python_interpreter, "-m", "pip", "install", "pdoc3"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            original_sys_path_inner = list(sys.path)

            sys.path.insert(0, venv_site_packages)
            print(f"Added {venv_site_packages} a sys.path")
            try:
                print("Executing generate_docs_from_folder con venv sys.path...")
                success = self.generate_docs_from_folder(
                    project_name,
                    str(cloned_repo_path),
                    str(tmp_output_dir),
                    modules_to_document=[project_name],
                    venv_python_interpreter=venv_python_interpreter,
                )

                if success:
                    print(
                        "Generating documentation completed successfully for"
                        f" {project_name}"
                    )
                    if final_output_dir.exists():
                        self.cleanup_folder(final_output_dir)
                    shutil.move(tmp_output_dir, final_output_dir)
                else:
                    print(
                        "documentation Generation failed or no documented module "
                        f"for {project_name}"
                    )

            finally:
                sys.path = original_sys_path_inner
                print(f"Removed {venv_site_packages} da sys.path")
                if tmp_output_dir.exists():
                    self.cleanup_folder(tmp_output_dir)
        except subprocess.CalledProcessError as cpe:
            print(f"\nERROR during execution of pip command: {cpe.cmd}")
            print(f"exit Code: {cpe.returncode}")
            print(f"Output del comando (stdout):\n---\n{cpe.stdout}\n---")
            print(f"Errors del comando (stderr):\n---\n{cpe.stderr}\n---")
        except RuntimeError as e:
            print(f"\nERROR during preparing phase (es. cloning): {e}")
        except Exception as e:
            print(f"\nUnexpected ERROR during il process di {project_name}: {e}")
            print("--- TRACEBACK ---")
            traceback.print_exc()
            print("--- FINE DETAIL ERROR UNEXPECTED ---")
        finally:
            print(f"Cleaning temporary folders for {project_name}...")
            if cloned_repo_path:
                self.cleanup_folder(cloned_repo_path)
            if temp_venv_path:
                self.cleanup_folder(temp_venv_path)
            print(f"Cleaning temporary folders for {project_name} completed.")


if __name__ == "__main__":
    P_URL = "https://github.com/psf/black"
    p_name = P_URL.rsplit("/", maxsplit=1)[-1]
    d_src = DocStringsSrc()
    d_src.run(P_URL, p_name)
