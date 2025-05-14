"""docstrings pdoc3 module."""

import importlib
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pdoc

from devildex import info
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command, install_project_and_dependencies_in_venv)

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
            self._log_traceback()
            return False

    def _is_pdoc_dummy_module(
        self, module_candidate: ModuleType | None, expected_name: str
    ) -> bool:
        """Checks if the imported object is a pdoc dummy module."""
        if (
            not module_candidate
        ):  # Can be None if pdoc.import_module itself returns None
            return True
        # A dummy module created by pdoc typically lacks __file__ and __path__,
        # and its __name__ might not match the expected_name if it's a placeholder.
        return (
            not hasattr(module_candidate, "__file__")
            and not hasattr(module_candidate, "__path__")
            and (
                not hasattr(module_candidate, "__name__")
                or module_candidate.__name__ != expected_name
            )
        )

    def _log_traceback(self):
         logger.debug("Traceback:", exc_info=True)

    def _perform_single_import(
        self, module_name: str
    ) -> tuple[ModuleType | None, Exception | None]:
        """Performs a single attempt to import the module using pdoc.

        Returns:
            - (module_object, None) on successful import of a real module.
            - (None, exception_object) if ModuleNotFoundError or ImportError occurs
              directly from pdoc.import_module (less common with skip_errors=True
              for simple missing deps, but possible for other import issues).
            - (None, None) if a dummy module is imported or another unexpected
              error occurs within pdoc.import_module that doesn't result in
              a direct ImportError/ModuleNotFoundError.
        """
        try:
            # pdoc.import_module with skip_errors=True might return a "dummy" module
            # instead of raising an error directly for missing dependencies.
            module_candidate = pdoc.import_module(
                module_name, reload=True, skip_errors=True
            )

            if self._is_pdoc_dummy_module(module_candidate, module_name):
                logger.debug(
                    "Module '%s' imported as a pdoc dummy object.", module_name
                )
                return (
                    None,
                    None,
                )  # Indicates dummy, not a specific ImportError from this call

            logger.debug("Successfully imported module '%s'.", module_name)
            return module_candidate, None  # Success, real module

        except ImportError as e:
            # This block is hit if pdoc.import_module itself raises these errors,
            # which can happen if the module name is invalid or pdoc cannot skip the error.
            logger.debug(
                "Import of '%s' failed within pdoc.import_module with: %s",
                module_name,
                e,
            )
            return None, e  # Specific import error that pdoc might re-raise

        except Exception as e:  # pylint: disable=broad-except
            # Catch other potential exceptions from pdoc.import_module
            logger.error(
                "Unexpected error during pdoc.import_module for '%s': %s",
                module_name,
                e,
            )
            self._log_traceback()
            return None, None  # Other error, not a specific ImportError to parse

    def _attempt_import_with_retry(
        self, module_name: str, venv_python_interpreter: str | None
    ) -> tuple[ModuleType | None, bool]:
        """Attempts to import a module, retrying once after attempting to install.

        a missing dependency if a venv interpreter is provided and a specific
        ImportError/ModuleNotFoundError was raised by pdoc.

        Returns (imported_module_object, dependency_installed_flag).
        The flag indicates if a dependency installation was successfully performed
        during this cycle.
        """
        dependency_installed = False

        # --- Attempt 1 ---
        logger.debug("Attempting to import module '%s' (Attempt 1)...", module_name)
        module_obj, import_error = self._perform_single_import(module_name)

        if module_obj:
            return module_obj, False  # Success on first try, no install attempted

        # --- Handling failure of Attempt 1 ---
        # If import_error is an actual ImportError/ModuleNotFoundError (not a dummy/other issue)
        # and we have a venv, try to parse the error and install the missing dependency.
        if import_error and venv_python_interpreter:
            missing_dep_name = self._extract_missing_module_name(str(import_error))
            if (
                missing_dep_name
                and missing_dep_name.strip()
                and missing_dep_name != module_name
            ):
                if self._attempt_install_missing_dependency(
                    missing_dep_name, venv_python_interpreter
                ):
                    dependency_installed = True
            else:
                logger.debug(
                    "Could not extract a valid missing dependency "
                    "name from error for '%s' (error: %s), "
                    "or it was the module itself. No install attempted based on this error.",
                    module_name,
                    import_error,
                )
        elif (
            not import_error
        ):  # Import resulted in dummy or other non-ImportError issue
            logger.debug(
                "Module '%s' import resulted in dummy or non-specific issue on attempt 1. "
                "Cannot attempt targeted dependency installation "
                "based on an error message.",
                module_name,
            )
        # If import_error is None (dummy/other) or no venv_python_interpreter,
        # we proceed to the second attempt without trying to install a dependency based on an error.

        # --- Attempt 2 (Always happens if Attempt 1 didn't return a module) ---
        logger.debug("Attempting to import module '%s' (Attempt 2)...", module_name)
        # The effect of a previous dependency installation (if any) will be tested here.
        module_obj_att2, _ = self._perform_single_import(module_name)
        # We don't act on the error from the 2nd attempt for further installations.

        if module_obj_att2:
            return module_obj_att2, dependency_installed

        # --- Failed after all attempts ---
        logger.info(
            "Module '%s' could not be imported or resulted in a dummy object after all attempts.",
            module_name,
        )
        return None, dependency_installed

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
            self._log_traceback()
            return None

    def _process_package_submodules(
        self, package_module_obj: ModuleType, context: pdoc.Context
    ) -> list[pdoc.Module]:
        """Iterates through a package's submodules, attempts to import and wrap each.

        Returns a list of successfully wrapped pdoc.Module instances for submodules.
        """
        processed_submodules: list[pdoc.Module] = []
        package_name = getattr(package_module_obj, "__name__", "unknown package")

        for submodule_info in pdoc.iter_submodules(package_module_obj):
            submodule_qualname = submodule_info.name
            logger.debug(
                "Attempting to process submodule '%s' of package '%s'.",
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
                self._log_traceback()

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
        module_obj, _ = self._attempt_import_with_retry(
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
        base_deps_for_pdoc_and_build = ["pdoc3"]
        install_deps_success = install_project_and_dependencies_in_venv(
            pip_executable=i_venv.pip_executable,
            project_name=project_name,
            project_root_for_install=source_project_path,
            doc_requirements_path=requirements_file,
            base_packages_to_install=base_deps_for_pdoc_and_build,
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

    def _validate_pdoc_output(
        self, pdoc_base_output_dir: Path, project_name: str
    ) -> str | None:
        """Checks if pdoc output directory and content are valid.

        Args:
            pdoc_base_output_dir: The base directory where pdoc was instructed to output.
            project_name: The name of the project, used to find the subdirectory.

        Returns:
            The path to the actual documentation content as a string if valid,
            otherwise None.
        """
        actual_docs_path = pdoc_base_output_dir / project_name
        if (
            actual_docs_path.exists()
            and actual_docs_path.is_dir()
            and any(actual_docs_path.iterdir())
        ):
            logger.info(
                "DocStringsSrc: pdoc content generated successfully in %s.",
                actual_docs_path,
            )
            return str(actual_docs_path)

        logger.warning(
            "DocStringsSrc: Expected pdoc content directory %s not found or empty.",
            actual_docs_path,
        )
        return None

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

        # pdoc_base_output_dir is where pdoc will create a subdirectory for project_name
        pdoc_base_output_dir = self._prepare_pdoc_output_directory(
            project_name, output_folder
        )
        if not pdoc_base_output_dir:  # _prepare_pdoc_output_directory logs errors
            return False

        requirements_file_to_install = self._find_pdoc_project_requirements(
            source_project_path, project_name
        )

        build_successful = False
        try:
            with IsolatedVenvManager(project_name=f"pdoc_{project_name}") as i_venv:
                # pdoc will write into pdoc_base_output_dir / project_name
                build_successful = self._execute_pdoc_build_in_venv(
                    i_venv,
                    project_name,
                    source_project_path,
                    requirements_file_to_install,
                    pdoc_base_output_dir,
                )
        except RuntimeError as e:  # Errors from IsolatedVenvManager.__enter__
            logger.error(
                "DocStringsSrc: Critical error during isolated pdoc "
                "build setup for %s: %s",
                project_name,
                e,
            )
            # build_successful remains False
        except Exception:  # Catch any other unexpected error during the 'with' block
            logger.exception(
                "DocStringsSrc: Unexpected exception during isolated pdoc build for %s.",
                project_name,
            )
            # build_successful remains False
        finally:
            logger.info("--- Finished Isolated pdoc Build for %s ---", project_name)

        # Process results and decide on cleanup
        if build_successful:
            validated_docs_path = self._validate_pdoc_output(
                pdoc_base_output_dir, project_name
            )
            if validated_docs_path:
                return validated_docs_path  # Success! Output dir remains for caller.

            # Build was marked successful, but content validation failed.
            logger.info(
                "DocStringsSrc: Build reported success, but content validation failed for %s. "
                "Cleaning up temporary output.",
                project_name,
            )
        else:
            # Build failed
            logger.info(
                "DocStringsSrc: pdoc build failed for %s. Cleaning up temporary output.",
                project_name,
            )

        # Common cleanup for build failure or content validation failure
        if pdoc_base_output_dir.exists():
            logger.info(
                "DocStringsSrc: Cleaning up pdoc base output directory %s.",
                pdoc_base_output_dir,
            )
            try:
                shutil.rmtree(pdoc_base_output_dir)
            except OSError as e_clean:
                logger.error(
                    "DocStringsSrc: Error cleaning up pdoc output directory %s: %s",
                    pdoc_base_output_dir,
                    e_clean,
                )
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

    def _handle_successful_doc_move(
        self, generated_content_path_str: str, final_docs_destination: Path
    ):
        """Handles moving generated docs to their final destination."""
        logger.info(
            "Documentation generated by isolated build at: %s",
            generated_content_path_str,
        )
        if final_docs_destination.exists():
            self.cleanup_folder(final_docs_destination)
        final_docs_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(generated_content_path_str), str(final_docs_destination))
        logger.info("Documentation moved to final location: %s", final_docs_destination)

    def _define_run_paths(
        self, project_name: str, version: str
    ) -> tuple[Path, Path, Path]:
        """Defines and returns standard paths used in the run method."""
        cloned_repo_path = Path(project_name)  # Relative to CWD for cloning

        final_docs_destination = self.docset_dir / project_name
        if version:  # McCabe +1
            final_docs_destination /= version

        temp_output_dirname = f"tmp_pdoc_output_{project_name}"
        if version:  # McCabe +1
            temp_output_dirname += f"_v{version}"
        pdoc_operation_basedir = self.docset_dir / temp_output_dirname

        return cloned_repo_path, final_docs_destination, pdoc_operation_basedir

    def _log_subprocess_error(
        self, cpe: subprocess.CalledProcessError, context_msg: str
    ):
        """Logs details of a CalledProcessError."""
        logger.error("%s: Subprocess execution failed: %s", context_msg, cpe.cmd)
        logger.error("%s: Exit Code: %s", context_msg, cpe.returncode)
        if cpe.stdout and cpe.stdout.strip():  # McCabe +1
            logger.debug("%s: Stdout:\n%s", context_msg, cpe.stdout.strip())
        if cpe.stderr and cpe.stderr.strip():  # McCabe +1
            logger.error("%s: Stderr:\n%s", context_msg, cpe.stderr.strip())

    def run(self, url: str, project_name: str, version: str = ""):
        """Main execution logic to clone, generate docs, and move to final location."""
        cloned_repo_path: Path | None = None
        pdoc_operation_basedir: Path | None = None
        generation_outcome: str | bool = False

        try:
            cloned_repo_path, final_docs_destination, pdoc_operation_basedir = (
                self._define_run_paths(project_name, version)
            )

            # Initial cleanup - paths from _define_run_paths are Path objects
            self.cleanup_folder(
                [cloned_repo_path, final_docs_destination, pdoc_operation_basedir]
            )

            self.git_clone(url, cloned_repo_path)

            logger.info("Calling generate_docs_from_folder for isolated build...")
            # cloned_repo_path and pdoc_operation_basedir are Path objects here
            generation_outcome = self.generate_docs_from_folder(
                project_name,
                str(cloned_repo_path.resolve()),
                str(pdoc_operation_basedir.resolve()),
            )

            if isinstance(generation_outcome, str):
                self._handle_successful_doc_move(
                    generation_outcome, final_docs_destination
                )
            else:
                logger.error(
                    "Documentation generation failed for %s using isolated build.",
                    project_name,
                )
        except subprocess.CalledProcessError as cpe:
            self._log_subprocess_error(cpe, f"Run phase for {project_name}")
        except RuntimeError as e:
            logger.error("Runtime error during run for %s: %s", project_name, e)
        except OSError as e:
            logger.error("OS error during run for %s: %s", project_name, e)
            self._log_traceback()
        except Exception:
            logger.exception(
                "Unexpected critical error during run for %s", project_name
            )
        finally:
            logger.info("Starting final cleanup for %s...", project_name)
            if cloned_repo_path and cloned_repo_path.exists():
                logger.info("Cleaning up cloned repository: %s", cloned_repo_path)
                self.cleanup_folder(cloned_repo_path)
            if pdoc_operation_basedir and pdoc_operation_basedir.exists():
                logger.info(
                    "Final cleanup of pdoc operation base directory: %s",
                    pdoc_operation_basedir,
                )
                self.cleanup_folder(pdoc_operation_basedir)
            logger.info("Final cleanup for %s completed.", project_name)


if __name__ == "__main__":
    P_URL = "https://github.com/psf/black"
    p_name = P_URL.rsplit("/", maxsplit=1)[-1]
    d_src = DocStringsSrc()
    d_src.run(P_URL, p_name)
