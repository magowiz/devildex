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

from devildex import info
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command,
    install_project_and_dependencies_in_venv,
)

logger = logging.getLogger(__name__)
CONFIG_FILE = "../../../devildex_config.ini"


class DocStringsSrc:
    """Implement class that build documentation from docstrings."""

    def __init__(self):
        """Initialize il DocStringsSrc."""
        project_root = info.PROJECT_ROOT
        self.docset_dir = project_root / "docset"
        self.docset_dir.mkdir(parents=True, exist_ok=True)

    def _attempt_install_missing_dependency(
        self, missing_module_name: str, venv_python_interpreter: str
    ) -> bool:
        """Attempts to install a missing dependency using pip in the venv.

        Returns True if installation was successful, False otherwise.
        """
        logger.info(
            "Attempting to install missing dependency '%s' using pip in venv...",
            missing_module_name,
        )
        try:
            # Use execute_command for consistency and better logging/error handling
            pip_install_cmd = [
                str(venv_python_interpreter),
                "-m",
                "pip",
                "install",
                missing_module_name,
            ]
            stdout, stderr, returncode = execute_command(
                pip_install_cmd,
                f"Install missing dependency {missing_module_name}",
            )

            if returncode == 0:
                logger.info(
                    "Installation of '%s' completed successfully.", missing_module_name
                )
                # Invalidate import caches before retrying import
                # This is crucial for import_module to pick up the newly installed package
                if missing_module_name in sys.modules:
                    del sys.modules[missing_module_name]
                importlib.invalidate_caches()
                return True
            logger.error(
                "Failed installation of '%s' (return code %d).",
                missing_module_name,
                returncode,
            )
            logger.debug("Install stdout:\n%s", stdout)
            logger.debug("Install stderr:\n%s", stderr)
            return False
        except Exception as pip_exec_err:
            logger.error(
                "Exception during attempt to install '%s': %s",
                missing_module_name,
                pip_exec_err,
            )
            logger.debug("Traceback:", exc_info=True)
            return False

    def _attempt_import_with_retry(
        self, module_name: str, venv_python_interpreter: str | None
    ) -> tuple[ModuleType | None, bool]:
        """Attempts to import a module, retrying once after attempting to install.

        a missing dependency if a venv interpreter is provided.
        Returns (imported_module_object, dependency_installed_flag).
        """
        module_obj: ModuleType | None = None
        dependency_installed = False

        for attempt in range(2):
            logger.debug(
                "Attempting to import module '%s' " "(Attempt %d)...",
                module_name,
                attempt + 1,
            )
            try:
                current_module_obj_candidate = pdoc.import_module(
                    module_name, reload=True, skip_errors=True
                )

                is_dummy = (
                    not hasattr(current_module_obj_candidate, "__file__")
                    and not hasattr(current_module_obj_candidate, "__path__")
                    and (
                        not hasattr(current_module_obj_candidate, "__name__")
                        or current_module_obj_candidate.__name__ != module_name
                    )
                )

                if is_dummy:
                    # If it's a dummy on the first attempt and we have a venv,
                    # treat it like an import error to trigger install attempt.
                    if attempt == 0 and venv_python_interpreter:
                        logger.debug(
                            "Module '%s' resulted in a dummy object on attempt 1. "
                            "Treating as import error to trigger dependency check.",
                            module_name,
                        )
                        module_obj = (
                            None  # Ensure it's None so the except block knows it failed
                        )
                        continue  # Go to the except block
                    logger.warning(
                        "Module '%s' resulted in a dummy object after attempts. Cannot process.",
                        module_name,
                    )
                    module_obj = None  # Explicitly set to None
                    break  # Final failure

                # If not a dummy, we got a module object
                module_obj = current_module_obj_candidate
                logger.debug(
                    "Successfully imported module '%s' on attempt %d.",
                    module_name,
                    attempt + 1,
                )
                break  # Success

            except (ModuleNotFoundError, ImportError) as import_err:
                logger.debug(
                    "Import failed for '%s' on attempt %d: %s",
                    module_name,
                    attempt + 1,
                    import_err,
                )
                module_obj = None  # Ensure module_obj is None on import failure

                # Only attempt install on the first failure and if venv interpreter is available
                if attempt == 0 and venv_python_interpreter:
                    missing_module_name = self._extract_missing_module_name(
                        str(import_err)
                    )

                    # Only attempt install if we found a missing module name
                    # and it's not the module we were originally trying to import
                    # (to avoid infinite loops if the module itself is the problem)
                    if (
                        missing_module_name
                        and missing_module_name.strip()
                        and missing_module_name != module_name
                    ):
                        # Call the new helper function
                        install_success = self._attempt_install_missing_dependency(
                            missing_module_name, venv_python_interpreter
                        )
                        if install_success:
                            dependency_installed = True
                            # Loop will continue to attempt 2 automatically
                        else:
                            # Installation failed, no point in retrying import
                            break
                    else:
                        # No missing module name extracted or it was the module itself
                        logger.debug(
                            "Could not extract a specific missing module name or it"
                            " was the target module '%s'. Cannot attempt dependency installation.",
                            module_name,
                        )
                        break
                else:
                    break

            except Exception as e:
                logger.error(
                    "An unexpected error occurred during import of '%s' on attempt %d: %s",
                    module_name,
                    attempt + 1,
                    e,
                )
                logger.debug("Traceback:", exc_info=True)
                module_obj = None
                break

        return module_obj, dependency_installed

    def _wrap_module_with_pdoc(
        self, module_obj: ModuleType, context: pdoc.Context
    ) -> pdoc.Module | None:
        """Wraps a valid module object with pdoc.Module.

        Returns the pdoc.Module instance or None if wrapping fails.
        """
        try:
            pdoc_module_instance = pdoc.Module(module_obj, context=context)
            logger.debug(
                "Successfully wrapped module '%s' with pdoc.",
                getattr(module_obj, "__name__", "unknown"),
            )
            return pdoc_module_instance
        except Exception as wrap_err:
            logger.error(
                "Error during pdoc wrapping of module '%s': %s",
                getattr(module_obj, "__name__", "unknown"),
                wrap_err,
            )
            logger.debug("Traceback:", exc_info=True)
            return None

    def _process_package_submodules(
        self, package_module_obj: ModuleType, context: pdoc.Context
    ) -> list[pdoc.Module]:
        """Iterates through a package's submodules, attempts to import and wrap each.

        Returns a list of successfully wrapped pdoc.Module instances for submodules.
        """
        processed_submodules: list[pdoc.Module] = []
        package_name = getattr(package_module_obj, "__name__", "unknown package")
        found_salvageable_submodule = False

        for submodule_info in pdoc.iter_submodules(package_module_obj):
            submodule_qualname = submodule_info.name
            logger.debug(
                "Attempting to process submodule '%s' of " "package '%s'.",
                submodule_qualname,
                package_name,
            )
            try:
                # Use skip_errors=False here as in the original code for submodules.
                # This means if a submodule import fails, it will raise an exception.
                submodule_actual_obj = pdoc.import_module(
                    submodule_qualname, reload=True, skip_errors=False
                )

                if not submodule_actual_obj:
                    logger.warning(
                        "Submodule '%s' of package '%s' imported but resulted in None. Skipping.",
                        submodule_qualname,
                        package_name,
                    )
                    continue  # Skip if import returned None

                sub_pdoc_instance = self._wrap_module_with_pdoc(
                    submodule_actual_obj, context
                )

                if sub_pdoc_instance:
                    processed_submodules.append(sub_pdoc_instance)
                    logger.info(
                        "Successfully recovered and wrapped submodule '%s'.",
                        submodule_qualname,
                    )
                    found_salvageable_submodule = True
                # _wrap_module_with_pdoc logs errors if wrapping fails

            except ImportError as sub_import_err:
                logger.warning(
                    "FAILED IMPORT (submodule): unable to import '%s' of package '%s': %s",
                    submodule_qualname,
                    package_name,
                    sub_import_err,
                )
            except Exception as sub_err:
                logger.error(
                    "An unexpected error occurred processing submodule '%s' of package '%s': %s",
                    submodule_qualname,
                    package_name,
                    sub_err,
                )
                logger.debug("Traceback:", exc_info=True)

        # The original code had a log here if no submodules were found.
        # The caller can check if the returned list is empty.
        return processed_submodules

    # La funzione _try_process_module rifattorizzata
    def _try_process_module(
        self,
        module_name_to_process: str,
        context: pdoc.Context,
        venv_python_interpreter: str | None,
    ) -> list[pdoc.Module]:
        """Attempts to import and wrap a module or its submodules with pdoc.

        optionally attempting to install missing dependencies.
        Returns a list of successfully wrapped pdoc.Module instances.
        """
        processed_pdoc_modules: list[pdoc.Module] = []

        logger.info("Attempting to process module '%s'...", module_name_to_process)

        # Step 1: Attempt to import the main module with retry logic
        module_obj, dependency_installed = self._attempt_import_with_retry(
            module_name_to_process, venv_python_interpreter
        )

        if module_obj:
            # Step 2: Try to wrap the main module
            pdoc_module_instance = self._wrap_module_with_pdoc(module_obj, context)

            if pdoc_module_instance:
                processed_pdoc_modules.append(pdoc_module_instance)
                logger.info(
                    "Main module '%s' successfully wrapped.", module_name_to_process
                )
            elif isinstance(module_obj, ModuleType) and hasattr(module_obj, "__path__"):
                # Step 3: If it's a package but couldn't be wrapped directly, process submodules
                logger.info(
                    "Main module '%s' imported as package but not wrapped."
                    " Attempting to recover submodules...",
                    module_name_to_process,
                )
                submodules = self._process_package_submodules(module_obj, context)
                processed_pdoc_modules.extend(submodules)
                if not submodules:
                    logger.info(
                        "No submodule of package '%s' successfully recovered.",
                        module_name_to_process,
                    )
            else:
                logger.info(
                    "Module '%s' imported but not wrapped and not "
                    "a package. No submodules to recover.",
                    module_name_to_process,
                )
        else:
            # Module import failed after retries (logged within _attempt_import_with_retry)
            logger.info(
                "Module '%s' could not be imported or resulted in a dummy "
                "object after attempts. Cannot process.",
                module_name_to_process,
            )

        # Log final outcome
        if processed_pdoc_modules:
            logger.info(
                "Finished processing '%s'. Successfully wrapped %d module(s)/submodule(s).",
                module_name_to_process,
                len(processed_pdoc_modules),
            )
        else:
            logger.warning(
                "Finished processing '%s'. No module(s)/submodule(s) were successfully wrapped.",
                module_name_to_process,
            )

        return processed_pdoc_modules

    def get_docset_dir(self):
        """Get docset dir."""
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

    def _prepare_pdoc_output_directory(
        self, project_name: str, base_output_str: str
    ) -> Path | None:
        """Prepares the output directory for pdoc, cleaning if necessary."""
        base_output_dir_for_pdoc = Path(base_output_str)
        final_project_pdoc_output_dir = base_output_dir_for_pdoc / project_name

        logger.info(
            "DocStringsSrc: Base output directory for pdoc outputs: %s",
            base_output_dir_for_pdoc,
        )
        logger.info(
            "DocStringsSrc: Final output directory for this project: %s",
            final_project_pdoc_output_dir,
        )
        if base_output_dir_for_pdoc.exists():
            logger.info(
                "DocStringsSrc: Removing existing base pdoc output directory: %s",  # CAMBIATO
                base_output_dir_for_pdoc,
            )
            try:
                shutil.rmtree(base_output_dir_for_pdoc)
            except OSError as e:
                logger.error(
                    "DocStringsSrc: Error removing %s: %s",
                    base_output_dir_for_pdoc,
                    e,
                )
                return None
        try:
            base_output_dir_for_pdoc.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(
                "DocStringsSrc: Error creating base output directory %s: %s",
                base_output_dir_for_pdoc,
                e,
            )
            return None
        return base_output_dir_for_pdoc

    def _find_pdoc_project_requirements(
        self, source_project_path: Path, project_name: str
    ) -> Path | None:
        """Finds a suitable requirements file for the project."""
        candidate_req_paths = [
            source_project_path / "requirements.txt",
            source_project_path / "dev-requirements.txt",
            source_project_path / "requirements-dev.txt",
            source_project_path / "docs" / "requirements.txt",
        ]
        for req_path_candidate in candidate_req_paths:
            if req_path_candidate.exists() and req_path_candidate.is_file():
                logger.info(
                    "DocStringsSrc: Found requirements file for dependencies: %s",
                    req_path_candidate,
                )
                return req_path_candidate
        logger.info(
            "DocStringsSrc: No general 'requirements.txt' found for %s "
            "in common locations. "
            "Will rely on project's setup (e.g., setup.py, pyproject.toml).",
            project_name,
        )
        return None

    def _execute_pdoc_build_in_venv(
        self,
        i_venv: IsolatedVenvManager,
        project_name: str,
        source_project_path: Path,
        requirements_file: Path | None,
        final_pdoc_output_path: Path,
    ) -> bool:
        """Installs dependencies and executes pdoc command in the venv."""
        logger.info(
            "DocStringsSrc: Created temporary venv for pdoc3 at %s",
            i_venv.venv_path,
        )

        install_deps_success = install_project_and_dependencies_in_venv(
            pip_executable=i_venv.pip_executable,
            project_name=project_name,
            project_root_for_install=source_project_path,
            doc_requirements_path=requirements_file,
            base_packages_to_install=["pdoc3"],
        )

        if not install_deps_success:
            logger.error(
                "DocStringsSrc: CRITICAL: Failed to install pdoc3 "
                "or project dependencies for %s in venv. Aborting pdoc3 build.",
                project_name,
            )
            return False

        # pdoc will create 'project_name' subdir in 'final_pdoc_output_path' if
        # 'project_name' is the module and '-o' points to 'final_pdoc_output_path'.
        # However, the original command was:
        # pdoc project_name -o final_pdoc_output_path
        # This means pdoc creates final_pdoc_output_path/project_name/...
        # The final_pdoc_output_path itself is what we want to return/check.
        pdoc_command = [
            i_venv.python_executable,
            "-m",
            "pdoc",
            "--html",
            project_name,  # The module to document
            "-o",
            str(final_pdoc_output_path.resolve()),
        ]

        logger.info("DocStringsSrc: Executing pdoc: %s", " ".join(pdoc_command))
        stdout, stderr, returncode = execute_command(
            pdoc_command,
            f"pdoc HTML generation for {project_name}",
            cwd=source_project_path,
        )

        if returncode == 0:
            logger.info(
                "DocStringsSrc: pdoc build for %s completed successfully.", project_name
            )
            return True

        logger.error(
            "DocStringsSrc: pdoc build for %s FAILED. Return code: %s",
            project_name,
            returncode,
        )
        logger.debug("pdoc stdout:\n%s", stdout)
        logger.debug("pdoc stderr:\n%s", stderr)
        return False

    def generate_docs_from_folder(
        self,
        project_name: str,
        input_folder: str,
        output_folder: str,  # This is the base directory for all pdoc outputs
    ) -> str | bool:
        """Genera documentazione HTML usando pdoc in un ambiente isolato."""
        logger.info("\n--- Starting Isolated pdoc Build for %s ---", project_name)
        source_project_path = Path(input_folder)
        logger.info(
            "DocStringsSrc: Project root (cloned input): %s", source_project_path
        )
        logger.info("DocStringsSrc: Module to document with pdoc: %s", project_name)

        final_project_pdoc_output_dir = self._prepare_pdoc_output_directory(
            project_name, output_folder
        )
        if not final_project_pdoc_output_dir:
            return False  # Error already logged

        requirements_file_to_install = self._find_pdoc_project_requirements(
            source_project_path, project_name
        )

        build_successful = False
        try:
            with IsolatedVenvManager(project_name=f"pdoc_{project_name}") as i_venv:
                build_successful = self._execute_pdoc_build_in_venv(
                    i_venv,
                    project_name,
                    source_project_path,
                    requirements_file_to_install,
                    final_project_pdoc_output_dir,  # pdoc will write into this_dir/project_name
                )
        except RuntimeError as e:  # Errors from IsolatedVenvManager.__enter__
            logger.error(
                "DocStringsSrc: Critical error during isolated pdoc "
                "build setup for %s: %s",
                project_name,
                e,
            )
        except Exception:  # Catch any other unexpected error during the 'with' block
            logger.exception(
                "DocStringsSrc: Unexpected exception during isolated pdoc build for %s.",
                project_name,
            )
        finally:
            logger.info("--- Finished Isolated pdoc Build for %s ---", project_name)

        if build_successful:
            actual_docs_path = final_project_pdoc_output_dir / project_name
            if actual_docs_path.exists() and actual_docs_path.is_dir() and any(actual_docs_path.iterdir()):
                logger.info(
                    "DocStringsSrc: pdoc content generated successfully in %s.",
                    actual_docs_path
                )
                return str(actual_docs_path)
            else:
                logger.warning(
                    "DocStringsSrc: pdoc build marked successful, but expected content directory %s not found or empty. "
                    "Returning False.",
                    actual_docs_path
                )
                if final_project_pdoc_output_dir.exists():
                    logger.info(
                        "DocStringsSrc: Cleaning up base pdoc output directory %s as specific project dir is missing or empty.",
                        final_project_pdoc_output_dir
                    )
                    try:
                        shutil.rmtree(final_project_pdoc_output_dir)
                    except OSError as e_clean:
                        logger.error("Error cleaning up %s: %s", final_project_pdoc_output_dir, e_clean)
                return False

        if final_project_pdoc_output_dir.exists():
            logger.info(
                "DocStringsSrc: Cleaning up partially created/failed pdoc output at %s "
                "due to build failure.",
                final_project_pdoc_output_dir,
            )
            try:
                shutil.rmtree(final_project_pdoc_output_dir)
            except OSError as e_clean:
                logger.error(
                    "DocStringsSrc: Error cleaning up failed pdoc output directory %s: %s",
                    final_project_pdoc_output_dir,
                    e_clean,
                )
        return False

        # ... (other methods like cleanup_folder, git_clone, _extract_missing_module_name, run)

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
                path_to_generated_docs_or_false = self.generate_docs_from_folder(
                    project_name,
                    str(cloned_repo_path),
                    str(tmp_output_dir)
                )

                if path_to_generated_docs_or_false:
                    print(
                        "Generating documentation completed successfully for"
                        f" {project_name}"
                    )
                    if final_output_dir.exists():
                        self.cleanup_folder(final_output_dir)
                    final_output_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(tmp_output_dir), str(final_output_dir))
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
        except OSError as e:
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
