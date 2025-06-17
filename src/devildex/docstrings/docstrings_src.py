"""docstrings pdoc3 module."""

import contextlib
import importlib
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Optional

import pdoc  # type: ignore[import-untyped]

from devildex import info
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command,
    install_project_and_dependencies_in_venv,
)

GIT_FULL_PATH = shutil.which("git")

logger = logging.getLogger(__name__)


@dataclass
class PDocContext:
    """Holds context for a pdoc build operation."""

    modules_to_document: list[str]
    pdoc_cwd: Path
    project_install_root: Path
    requirements_file: Path | None
    pdoc_command_output_dir: Path
    project_name_for_log: str


class GitCloneFailedUnknownReasonError(RuntimeError):
    """Exception raised when a git clone operation fails for an unknown reason.

    after attempting to clone specified branches.
    """

    def __init__(self, repo_url: str, branches_tried: list[str]) -> None:
        """Construct a GitCloneFailedUnknownReasonError object."""
        self.repo_url = repo_url
        self.branches_tried = branches_tried
        message = (
            f"Could not clone repository {self.repo_url} from branches "
            f"{', '.join(self.branches_tried)}. "
            "Unknown reason if no specific git error was logged."
        )
        super().__init__(message)


class DocStringsSrc:
    """Implement class that build documentation from docstrings."""

    def __init__(
        self, template_dir: Optional[Path] = None, output_dir: Path | str | None = None
    ) -> None:
        """Initialize il DocStringsSrc."""
        project_root = info.PROJECT_ROOT
        if output_dir:
            self.docset_dir = Path(output_dir).resolve()
        else:
            self.docset_dir = (project_root / "docset").resolve()
        self.docset_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir = template_dir

    def _build_pdoc_command(
        self,
        python_executable: str,
        modules_to_document: list[str],
        output_directory: Path,
    ) -> list[str]:
        """Build the list of arguments for the PDOC command."""
        if not modules_to_document:

            logger.error(
                "DocstringsSrc: No module specified for PDOC. "
                "Impossible to build the command."
            )

            return []

        main_module_for_pdoc = modules_to_document[0]

        pdoc_command_args = [
            python_executable,
            "-m",
            "pdoc",
            "--html",
            "--skip-errors",
        ]

        if self.template_dir:
            logger.info(
                "Using customized template directory: %s",
                self.template_dir,
            )
            pdoc_command_args.extend(
                ["--template-dir", str(self.template_dir.resolve())]
            )

        pdoc_command_args.extend(
            [
                "-o",
                str(output_directory.resolve()),
            ]
        )

        pdoc_command_args.append(main_module_for_pdoc)

        return pdoc_command_args

    def _copy_theme_static_files(self, validated_docs_path: Path) -> None:
        """Copy static files from the theme directory if specified."""
        if self.template_dir and (self.template_dir / "static").is_dir():
            source_static_dir = self.template_dir / "static"
            destination_static_dir: Path

            if validated_docs_path.is_dir():
                destination_static_dir = validated_docs_path / "static"
            elif validated_docs_path.is_file():
                destination_static_dir = validated_docs_path.parent / "static"
            else:
                logger.error(
                    "DocStringsSrc: Validated docs path %s is "
                    "neither file nor dir for static copy.",
                    validated_docs_path,
                )
                return

            if destination_static_dir.exists() and not destination_static_dir.is_dir():
                logger.warning(
                    "DocStringsSrc: Static destination %s exists but is not"
                    " a directory. Removing it.",
                    destination_static_dir,
                )
                destination_static_dir.unlink()

            destination_static_dir.mkdir(parents=True, exist_ok=True)

            shutil.copytree(
                source_static_dir, destination_static_dir, dirs_exist_ok=True
            )

            logger.info(
                "DocstringsSrc: copied static files from the theme to %s",
                destination_static_dir,
            )

    def _handle_successful_pdoc_generation(
        self,
        validated_docs_path_str: str,
        source_project_path: Path,
    ) -> str:
        """Handle post-processing after a successful pdoc build and validation."""
        validated_docs_path = Path(validated_docs_path_str)
        self._copy_theme_static_files(validated_docs_path)

        report_file = validated_docs_path / "non_package_folders_report.txt"
        self._find_and_report_non_package_folders(
            scan_base_path=source_project_path,
            project_root_for_relative_paths=source_project_path,
            output_report_file=report_file,
        )

        if report_file.exists():
            self._process_reported_folders(
                report_file_path=report_file,
                pdoc_project_output_path=validated_docs_path,
            )
        return validated_docs_path_str

    @staticmethod
    def _cleanup_pdoc_output_on_failure(
        pdoc_command_output_dir: Path, project_name: str
    ) -> None:
        """Clean up pdoc output directories in case of a build/validation failure."""
        project_specific_output_dir = pdoc_command_output_dir / project_name
        if project_specific_output_dir.exists():
            logger.info(
                "DocStringsSrc: Cleaning up pdoc project specific output directory %s.",
                project_specific_output_dir,
            )
            try:
                shutil.rmtree(project_specific_output_dir)
                if pdoc_command_output_dir.exists() and not any(
                    pdoc_command_output_dir.iterdir()
                ):
                    shutil.rmtree(pdoc_command_output_dir)
                    logger.info(
                        "DocStringsSrc: Removed empty base pdoc output directory %s.",
                        pdoc_command_output_dir,
                    )
            except OSError:
                logger.exception(
                    "DocStringsSrc: Error cleaning up pdoc output directory %s",
                    project_specific_output_dir,
                )
        elif pdoc_command_output_dir.exists():
            logger.info(
                "DocStringsSrc: Cleaning up base pdoc output directory %s "
                "as project specific dir was not found.",
                pdoc_command_output_dir,
            )
            try:
                shutil.rmtree(pdoc_command_output_dir)
            except OSError:
                logger.exception(
                    "DocStringsSrc: Error cleaning up base pdoc output directory %s",
                    pdoc_command_output_dir,
                )

    def generate_docs_from_folder(
        self,
        project_name: str,
        input_folder: str,
        output_folder: str,
    ) -> str | bool:
        """Generate HTML documentation using PDOC in an isolated environment."""
        logger.info("\n--- Starting Isolated pdoc Build for %s ---", project_name)

        source_project_path = Path(input_folder) / project_name
        if not source_project_path.is_dir():
            logger.error(
                "DocstringsSrc: The Specified Source Project Folder does not exist: %s",
                source_project_path,
            )
            logger.error(
                "DocstringsSrc: Details - input_folder: '%s', project_name: '%s'",
                input_folder,
                project_name,
            )
            return False

        logger.info(
            "DocStringsSrc: Project source root for pdoc: %s", source_project_path
        )
        logger.info(
            "DocStringsSrc: Main package to document with pdoc: %s", project_name
        )

        modules_for_pdoc_command = [project_name]

        logger.info(
            "DocstringsSrc: modules/packages to go to PDOC: %s",
            modules_for_pdoc_command,
        )

        pdoc_command_output_dir = self._prepare_pdoc_output_directory(
            project_name,
            output_folder,
        )
        if not pdoc_command_output_dir:
            return False

        requirements_file_to_install = self._find_pdoc_project_requirements(
            source_project_path, project_name
        )

        build_successful = False
        try:
            with IsolatedVenvManager(project_name=f"pdoc_{project_name}") as i_venv:
                pdoc_exec_context = PDocContext(
                    modules_to_document=modules_for_pdoc_command,
                    pdoc_cwd=Path(input_folder),
                    project_install_root=source_project_path,
                    requirements_file=requirements_file_to_install,
                    pdoc_command_output_dir=pdoc_command_output_dir,
                    project_name_for_log=project_name,
                )
                build_successful = self._execute_pdoc_build_in_venv(
                    i_venv,
                    pdoc_exec_context,
                )
        except RuntimeError:
            logger.exception(
                "DocStringsSrc: Critical error during isolated pdoc build setup for %s",
                project_name,
            )
        except (KeyboardInterrupt, SystemExit):
            logger.warning(
                "DocStringsSrc: Isolated pdoc build for %s "
                "interrupted or system exit called.",
                project_name,
            )
            raise
        finally:
            logger.info("--- Finished Isolated pdoc Build for %s ---", project_name)

        if build_successful:
            validated_docs_path_str = self._validate_pdoc_output(
                pdoc_command_output_dir, project_name
            )
            if validated_docs_path_str:
                return self._handle_successful_pdoc_generation(
                    validated_docs_path_str, source_project_path
                )

            logger.info(
                "DocStringsSrc: Build reported success, "
                "but content validation failed for %s. "
                "Cleaning up temporary output.",
                project_name,
            )
        else:
            logger.info(
                "DocStringsSrc: pdoc build failed for %s. "
                "Cleaning up temporary output.",
                project_name,
            )

        self._cleanup_pdoc_output_on_failure(pdoc_command_output_dir, project_name)
        return False

    @staticmethod
    def _find_and_report_non_package_folders(
        scan_base_path: Path,
        project_root_for_relative_paths: Path,
        output_report_file: Path,
    ) -> None:
        """Scan recursively scan_base_path for folders that are not packages.

        (i.e., they do not contain __init__.py) and writes their relative paths
        A Project_root_for_relative_paths in the Output_report_file file.
        """
        non_package_folders: list[Path] = []

        def find_recursively(current_path: Path) -> None:
            for item in current_path.iterdir():
                if item.name.startswith((".", "__")) or item.name == "site-packages":
                    continue
                if item.is_dir():
                    if not (item / "__init__.py").exists():
                        non_package_folders.append(
                            item.relative_to(project_root_for_relative_paths)
                        )
                    find_recursively(item)

        logger.info(
            "DocstringsSrc: Start scan for non-Package folders in: %s", scan_base_path
        )

        find_recursively(scan_base_path)

        if non_package_folders:
            try:
                output_report_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_report_file, "w", encoding="utf-8") as f:
                    f.write(
                        f"Non-Package folders (without __init__py) found inside "
                        f"'{project_root_for_relative_paths.name}':\n"
                    )

                    for folder_path in sorted(non_package_folders):
                        f.write(f"- {folder_path}\n")
                logger.info(
                    "DocstringsSrc: Report of non-Package folders saved in: %s",
                    output_report_file,
                )

            except OSError:
                logger.exception(
                    "DocstringsSrc: Error when writing the report of "
                    "non-Package folders in %s",
                    output_report_file,
                )

        else:
            logger.info(
                "DocstringsSrc: no non-payroll folders found in '%s'."
                " No reports generated.",
                scan_base_path.name,
            )

    @staticmethod
    def _read_non_package_report(report_file_path: Path) -> list[str]:
        """Read the report and return a list of non-Package folders."""
        reported_relative_paths: list[str] = []
        if not report_file_path.exists():
            logger.warning(
                "DocstringsSrc: Non-Package Report file not found: %s",
                report_file_path,
            )
            return reported_relative_paths

        try:
            with open(report_file_path, encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines[1:]:
                stripped_line = line.strip()
                if stripped_line.startswith("- "):
                    relative_path = stripped_line[2:].strip()
                    if relative_path:
                        reported_relative_paths.append(relative_path)
            logger.info(
                "DocStringsSrc: Letti %d path dal report non-package: %s",
                len(reported_relative_paths),
                report_file_path,
            )
        except OSError:
            logger.exception(
                "DocstringsSrc: error while reading the non-Package report %s",
                report_file_path,
            )
        return reported_relative_paths

    @staticmethod
    def _remove_links_from_html_content(
        html_content: str, folder_to_remove_links_for: str
    ) -> str:
        """Remove the HTML links that aim for the specified folder or its content.

        Also removes list items that textually refer to the folder.
        """
        logger.info("--- START _remove_links_from_html_content ---")

        current_processing_content = html_content

        folder_display_name = Path(folder_to_remove_links_for).name
        escaped_folder_display_name = re.escape(folder_display_name)

        simple_href_pattern_part = re.escape(
            folder_to_remove_links_for.replace(os.sep, "/")
        )
        logger.info("--- Trying PATTERN 0.A (Specific <li> for 'docs/') ---")
        specific_li_pattern_str = (
            r"<li[^>]*>"
            r"\s*<code[^>]*>\s*"
            r"<a\s+[^>]*href\s*=\s*[\"']"
            rf"{simple_href_pattern_part}/[^\"'>\s]*[\"']"
            r"[^>]*>.*?</a>\s*"
            r"</code>\s*</li>"
        )
        specific_li_pattern = re.compile(
            specific_li_pattern_str, re.IGNORECASE | re.DOTALL
        )

        matches_0a = list(specific_li_pattern.finditer(current_processing_content))
        if matches_0a:
            current_processing_content = specific_li_pattern.sub(
                "", current_processing_content
            )

        logger.info("--- Trying PATTERN 0.B (Specific <dt>...<dd> for 'docs/') ---")
        specific_dt_dd_pattern_str = (
            r"<dt[^>]*>\s*<code[^>]*>\s*"
            r"<a\s+[^>]*href\s*=\s*[\"']"
            rf"{simple_href_pattern_part}/[^\"'>\s]*[\"']"
            r"[^>]*>.*?</a>\s*"
            r"</code>\s*</dt>\s*"
            r"<dd.*?</dd>"
        )
        specific_dt_dd_pattern = re.compile(
            specific_dt_dd_pattern_str, re.IGNORECASE | re.DOTALL
        )

        matches_0b = list(specific_dt_dd_pattern.finditer(current_processing_content))
        if matches_0b:
            current_processing_content = specific_dt_dd_pattern.sub(
                "", current_processing_content
            )
        logger.info("--- Trying PATTERN 1 (Generic <a> for 'docs/') ---")
        link_pattern_str_1 = (
            r'<a\s+[^>]*href\s*=\s*["\']'
            rf"({simple_href_pattern_part}(?:/[^\"\'\s]*)?)"
            r'["\'][^>]*>.*?</a>'
        )
        link_pattern_1 = re.compile(link_pattern_str_1, re.IGNORECASE | re.DOTALL)

        matches_1 = list(link_pattern_1.finditer(current_processing_content))
        if matches_1:
            content_after_pattern_1 = link_pattern_1.sub("", current_processing_content)
            if content_after_pattern_1 != current_processing_content:
                current_processing_content = content_after_pattern_1

        logger.info(
            "--- Trying PATTERN 2 (<li> with <a> to 'docs/' AND text 'docs') ---"
        )
        list_item_with_link_pattern_str_2 = (
            r"<li[^>]*>\s*"
            r'<a\s+[^>]*href\s*=\s*["\']'
            rf"({simple_href_pattern_part}(?:/[^\"\'\s]*)?)"
            r'["\'][^>]*>\s*'
            rf"{escaped_folder_display_name}\s*</a>"
            r"\s*</li>"
        )
        list_item_with_link_pattern_2 = re.compile(
            list_item_with_link_pattern_str_2, re.IGNORECASE | re.DOTALL
        )

        content_after_pattern_2 = list_item_with_link_pattern_2.sub(
            "", current_processing_content
        )
        if content_after_pattern_2 != current_processing_content:
            current_processing_content = content_after_pattern_2

        logger.info("--- Trying PATTERN 3 (<li> with text 'docs') ---")
        list_item_text_pattern_str_3 = (
            r"<li[^>]*>"
            r"\s*(?:<code[^>]*>\s*)?"
            rf"{escaped_folder_display_name}"
            r"(?:\s*</code[^>]*>)?"
            r"\s*</li>"
        )
        list_item_text_pattern_3 = re.compile(
            list_item_text_pattern_str_3, re.IGNORECASE | re.DOTALL
        )

        content_after_pattern_3 = list_item_text_pattern_3.sub(
            "", current_processing_content
        )
        if content_after_pattern_3 != current_processing_content:
            current_processing_content = content_after_pattern_3

        logger.info("--- END _remove_links_from_html_content ---")
        return current_processing_content

    def _clean_html_file_for_reported_path(
        self,
        html_file: Path,
        reported_folder_path: str,
        empty_li_pattern: re.Pattern,
        empty_dt_dd_pattern: re.Pattern,
    ) -> None:
        """Clean an HTML file removing links and tags related to a reported folder."""
        try:
            original_content = html_file.read_text(encoding="utf-8")
            current_content = original_content

            content_after_link_removal = self._remove_links_from_html_content(
                current_content, reported_folder_path
            )
            if content_after_link_removal != current_content:
                logger.debug(
                    "DocstringsSrc: removed links to ' %s' from %s",
                    reported_folder_path,
                    html_file,
                )
                current_content = content_after_link_removal

            content_after_empty_li_cleanup = empty_li_pattern.sub("", current_content)
            if content_after_empty_li_cleanup != current_content:
                logger.debug(
                    "DocstringsSrc: Clean <li> <Code> </code> "
                    "</li> Empty from %s (relative to %s)",
                    html_file,
                    reported_folder_path,
                )
                current_content = content_after_empty_li_cleanup

            content_after_empty_dt_dd_cleanup = empty_dt_dd_pattern.sub(
                "", current_content
            )
            if content_after_empty_dt_dd_cleanup != current_content:
                logger.debug(
                    "DocstringsSrc: clean <dt> <code> </code> </ dt> "
                    "<dd> ... </dd> empty from %s (relative to %s)",
                    html_file,
                    reported_folder_path,
                )
                current_content = content_after_empty_dt_dd_cleanup

            if current_content != original_content:
                html_file.write_text(current_content, encoding="utf-8")
                logger.info(
                    "DocstringsSrc: modified HTML %s file for "
                    "cleaning relating to %s",
                    html_file,
                    reported_folder_path,
                )
        except OSError:
            logger.exception(
                "DocstringsSrc: error during processing the HTML %s"
                " file for removing links/cleaning.",
                html_file,
            )

    def _process_reported_folders(
        self, report_file_path: Path, pdoc_project_output_path: Path
    ) -> None:
        """Read the report of the non-Package folders, delete them from the output.

        and tries to remove the links to them from the HTML files, including cleaning
        of any tags remained empty.
        """
        relative_paths_to_process = self._read_non_package_report(report_file_path)
        if not relative_paths_to_process:
            logger.info(
                "DocstringsSrc: no path to be tried from the non-payable report."
            )
            return

        empty_li_pattern = re.compile(
            r"<li[^>]*>\s*<code>\s*</code>\s*</li>", re.IGNORECASE | re.DOTALL
        )
        empty_dt_dd_pattern = re.compile(
            r"<dt[^>]*>\s*<code[^>]*>\s*</code>\s*</dt>\s*<dd[^>]*>.*?</dd>",
            re.IGNORECASE | re.DOTALL,
        )

        for rel_path_str in relative_paths_to_process:
            folder_to_delete_in_pdoc_output = pdoc_project_output_path / rel_path_str
            if (
                folder_to_delete_in_pdoc_output.exists()
                and folder_to_delete_in_pdoc_output.is_dir()
            ):
                try:
                    shutil.rmtree(folder_to_delete_in_pdoc_output)
                    logger.info(
                        "DocstringsSrc: canceled non-packing folder from "
                        "the PDOC Output: %s",
                        folder_to_delete_in_pdoc_output,
                    )
                except OSError:
                    logger.exception(
                        "DocstringsSrc: Error during the cancellation of the %s "
                        "folder from the PDOC output.",
                        folder_to_delete_in_pdoc_output,
                    )
            else:
                logger.debug(
                    "DocstringsSrc: delete folder not found in the PDOC Output "
                    "(or is not a dir): %s",
                    folder_to_delete_in_pdoc_output,
                )
            logger.info(
                "DocstringsSrc: attempt to removal links and cleaning for ' %s'"
                " from html files in %s",
                rel_path_str,
                pdoc_project_output_path,
            )
            for html_file in pdoc_project_output_path.rglob("*.html"):
                self._clean_html_file_for_reported_path(
                    html_file, rel_path_str, empty_li_pattern, empty_dt_dd_pattern
                )

        try:
            report_file_path.unlink(missing_ok=True)
            logger.info("DocstringsSrc: deleted report files: %s", report_file_path)

        except OSError:
            logger.exception(
                "DocstringsSrc: Error when deleting the Report %s file",
                report_file_path,
            )

    @staticmethod
    def _attempt_install_missing_dependency(
        missing_module_name: str, venv_python_interpreter: str
    ) -> bool:
        """Attempt to install a missing dependency using pip in the venv.

        Returns True if installation was successful, False otherwise.
        """
        logger.info(
            "Attempting to install missing dependency '%s' using pip in venv...",
            missing_module_name,
        )
        pip_install_cmd = [
            str(venv_python_interpreter),
            "-m",
            "pip",
            "install",
            missing_module_name,
        ]
        stdout, stderr, return_code = execute_command(
            pip_install_cmd,
            f"Install missing dependency {missing_module_name}",
        )

        if return_code == 0:
            logger.info(
                "Installation of '%s' completed successfully.", missing_module_name
            )
            if missing_module_name in sys.modules:
                del sys.modules[missing_module_name]
            importlib.invalidate_caches()
            return True
        logger.error(
            "Failed installation of '%s' (return code %d).",
            missing_module_name,
            return_code,
        )
        logger.debug("Install stdout:\n%s", stdout)
        logger.debug("Install stderr:\n%s", stderr)
        return False

    @staticmethod
    def _is_pdoc_dummy_module(
        module_candidate: ModuleType | None, expected_name: str
    ) -> bool:
        """Check if the imported object is a pdoc dummy module."""
        if not module_candidate:
            return True
        return (
            not hasattr(module_candidate, "__file__")
            and not hasattr(module_candidate, "__path__")
            and (
                not hasattr(module_candidate, "__name__")
                or module_candidate.__name__ != expected_name
            )
        )

    @staticmethod
    def _log_traceback() -> None:
        logger.debug("Traceback:", exc_info=True)

    def _perform_single_import(
        self, module_name: str
    ) -> tuple[ModuleType | None, Exception | None]:
        """Perform a single attempt to import the module using pdoc.

        Returns:
            - module_object: on successful import of a real module.
            - (None, exception_object) if ModuleNotFoundError or ImportError occurs
              directly from pdoc.import_module (less common with skip_errors=True
              for simple missing deps, but possible for other import issues).
            - (None, None) if a dummy module is imported or another unexpected
              error occurs within pdoc.import_module that doesn't result in
              a direct ImportError/ModuleNotFoundError.

        """
        try:
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
                )

            logger.debug("Successfully imported module '%s'.", module_name)

        except ImportError as e:
            logger.debug(
                "Import of '%s' failed within pdoc.import_module with: %s",
                module_name,
                e,
            )
            return None, e

        except RuntimeError:
            logger.exception(
                "Unexpected error during pdoc.import_module for '%s'", module_name
            )
            return None, None
        else:
            return module_candidate, None

    def _attempt_import_with_retry(
        self, module_name: str, venv_python_interpreter: str | None
    ) -> tuple[ModuleType | None, bool]:
        """Attempt to import a module, retrying once after attempting to install.

        a missing dependency if a venv interpreter is provided and a specific
        ImportError/ModuleNotFoundError was raised by pdoc.

        Returns (imported_module_object, dependency_installed_flag).
        The flag indicates if a dependency installation was successfully performed
        during this cycle.
        """
        dependency_installed = False

        logger.debug("Attempting to import module '%s' (Attempt 1)...", module_name)
        module_obj, import_error = self._perform_single_import(module_name)

        if module_obj:
            return module_obj, False

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
                    "or it was the module itself. No install attempted "
                    "based on this error.",
                    module_name,
                    import_error,
                )
        elif not import_error:
            logger.debug(
                "Module '%s' import resulted in dummy or non-specific "
                "issue on attempt 1. "
                "Cannot attempt targeted dependency installation "
                "based on an error message.",
                module_name,
            )

        logger.debug("Attempting to import module '%s' (Attempt 2)...", module_name)
        module_obj_att2, _ = self._perform_single_import(module_name)

        if module_obj_att2:
            return module_obj_att2, dependency_installed

        logger.info(
            "Module '%s' could not be imported or resulted in "
            "a dummy object after all attempts.",
            module_name,
        )
        return None, dependency_installed

    @staticmethod
    def _wrap_module_with_pdoc(
        module_obj: ModuleType, context: pdoc.Context
    ) -> pdoc.Module:
        """Wrap a valid module object with pdoc.Module.

        Returns the pdoc.Module instance.
        Raises an exception if pdoc.Module() fails.
        """
        pdoc_module_instance = pdoc.Module(module_obj, context=context)
        logger.debug(
            "Successfully wrapped module '%s' with pdoc.",
            getattr(module_obj, "__name__", "unknown"),
        )
        return pdoc_module_instance

    def _discover_python_modules_and_packages(
        self, base_path: Path, current_package_qualname: str = ""
    ) -> list[str]:
        """Discover recursively valid Python and packages.

        Return a list of qualified names to move on to PDOC.
        """
        entities: list[str] = []
        for item in base_path.iterdir():
            if item.name.startswith((".", "__")):
                continue

            potential_module_name_part = item.stem if item.is_file() else item.name

            if item.is_file() and item.name.endswith(".py"):
                if item.name == "__init__.py":
                    continue
                entities.append(
                    f"{current_package_qualname}.{potential_module_name_part}"
                )
            elif item.is_dir() and (item / "__init__.py").exists():
                sub_package_qname = (
                    f"{current_package_qualname}.{potential_module_name_part}"
                )
                entities.append(sub_package_qname)
                entities.extend(
                    self._discover_python_modules_and_packages(item, sub_package_qname)
                )

        return entities

    def _process_package_submodules(
        self, package_module_obj: ModuleType, context: pdoc.Context
    ) -> list[pdoc.Module]:
        """Iterate through a package's submodules, attempts to import and wrap each.

        Returns a list of successfully wrapped pdoc.Module instances for submodules.
        """
        processed_submodules: list[pdoc.Module] = []
        package_name = getattr(package_module_obj, "__name__", "unknown package")

        for submodule_info in pdoc.iter_submodules(  # pylint: disable=no-member
            package_module_obj
        ):
            submodule_qualname = submodule_info.name
            logger.debug(
                "Attempting to process submodule '%s' of package '%s'.",
                submodule_qualname,
                package_name,
            )
            try:
                submodule_actual_obj = pdoc.import_module(
                    submodule_qualname, reload=True, skip_errors=False
                )

                if not submodule_actual_obj:
                    logger.warning(
                        "Submodule '%s' of package '%s' "
                        "imported but resulted in None. Skipping.",
                        submodule_qualname,
                        package_name,
                    )
                    continue

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
                    "FAILED IMPORT (submodule): unable to import '%s' "
                    "of package '%s': %s",
                    submodule_qualname,
                    package_name,
                    sub_import_err,
                )
        return processed_submodules

    def _try_process_module(
        self,
        module_name_to_process: str,
        context: pdoc.Context,
        venv_python_interpreter: str | None,
    ) -> list[pdoc.Module]:
        """Attempt to import and wrap a module or its submodules with pdoc.

        optionally attempting to install missing dependencies.
        Returns a list of successfully wrapped pdoc.Module instances.
        """
        processed_pdoc_modules: list[pdoc.Module] = []

        logger.info("Attempting to process module '%s'...", module_name_to_process)

        module_obj, _ = self._attempt_import_with_retry(
            module_name_to_process, venv_python_interpreter
        )

        if module_obj:
            pdoc_module_instance = self._wrap_module_with_pdoc(module_obj, context)

            if pdoc_module_instance:
                processed_pdoc_modules.append(pdoc_module_instance)
                logger.info(
                    "Main module '%s' successfully wrapped.", module_name_to_process
                )
            elif isinstance(module_obj, ModuleType) and hasattr(module_obj, "__path__"):
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
            logger.info(
                "Module '%s' could not be imported or resulted in a dummy "
                "object after attempts. Cannot process.",
                module_name_to_process,
            )

        if processed_pdoc_modules:
            logger.info(
                "Finished processing '%s'. "
                "Successfully wrapped %d module(s)/submodule(s).",
                module_name_to_process,
                len(processed_pdoc_modules),
            )
        else:
            logger.warning(
                "Finished processing '%s'. "
                "No module(s)/submodule(s) were successfully wrapped.",
                module_name_to_process,
            )

        return processed_pdoc_modules

    def get_docset_dir(self) -> Path:
        """Get docset dir."""
        return self.docset_dir

    @staticmethod
    def _discover_modules_in_folder(input_folder_path: Path) -> list[str]:
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

    @staticmethod
    def _prepare_pdoc_output_directory(
        project_name: str, base_output_str: str
    ) -> Path | None:
        """Prepare the output directory for pdoc, cleaning if necessary."""
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
                "DocStringsSrc: Removing existing base pdoc output directory: %s",
                base_output_dir_for_pdoc,
            )
            try:
                shutil.rmtree(base_output_dir_for_pdoc)
            except OSError:
                logger.exception(
                    "DocStringsSrc: Error removing %s",
                    base_output_dir_for_pdoc,
                )
                return None
        try:
            base_output_dir_for_pdoc.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception(
                "DocStringsSrc: Error creating base output directory %s",
                base_output_dir_for_pdoc,
            )
            return None
        return base_output_dir_for_pdoc

    @staticmethod
    def _find_pdoc_project_requirements(
        source_project_path: Path, project_name: str
    ) -> Path | None:
        """Find a suitable requirements file for the project."""
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
        pdoc_context: PDocContext,
    ) -> bool:
        """Installs dependencies and executes pdoc command in the venv."""
        logger.info(
            "DocStringsSrc: Created temporary venv for pdoc3 at %s",
            i_venv.venv_path,
        )
        base_deps_for_pdoc_and_build = ["pdoc3"]
        install_deps_success = install_project_and_dependencies_in_venv(
            pip_executable=i_venv.pip_executable,
            project_name=pdoc_context.project_name_for_log,
            project_root_for_install=pdoc_context.project_install_root,
            doc_requirements_path=pdoc_context.requirements_file,
            base_packages_to_install=base_deps_for_pdoc_and_build,
        )

        if not install_deps_success:
            logger.error(
                "DocStringsSrc: CRITICAL: Failed to install pdoc3 "
                "or project dependencies for %s in venv. Aborting pdoc3 build.",
                pdoc_context.project_name_for_log,
            )
            return False

        pdoc_command = self._build_pdoc_command(
            i_venv.python_executable,
            pdoc_context.modules_to_document,
            pdoc_context.pdoc_command_output_dir,
        )
        if not pdoc_command:
            return False

        logger.info("DocStringsSrc: Executing pdoc: %s", " ".join(pdoc_command))
        logger.info("DocStringsSrc: pdoc CWD: %s", pdoc_context.pdoc_cwd)
        stdout, stderr, return_code = execute_command(
            pdoc_command,
            f"pdoc HTML generation for {pdoc_context.project_name_for_log}",
            cwd=pdoc_context.pdoc_cwd,
        )

        if return_code == 0:
            logger.info(
                "DocStringsSrc: pdoc build for %s completed successfully.",
                pdoc_context.project_name_for_log,
            )

            return True

        logger.error(
            "DocStringsSrc: pdoc build for %s FAILED. Return code: %s",
            pdoc_context.project_name_for_log,
            return_code,
        )
        logger.debug("pdoc stdout:\n%s", stdout)
        logger.debug("pdoc stderr:\n%s", stderr)

        return False

    @staticmethod
    def _validate_pdoc_output(
        pdoc_base_output_dir: Path, project_name: str
    ) -> str | None:
        """Check if pdoc output directory or file content are valid.

        Args:
            pdoc_base_output_dir: The base directory where pdoc was
                instructed to output.
            project_name: The name of the project, used to find the subdirectory
                          or the specific HTML file.

        Returns:
            The path to the actual documentation content (directory or file)
            as a string if valid, otherwise None.

        """
        project_specific_output_dir = pdoc_base_output_dir / project_name
        if (
            project_specific_output_dir.exists()
            and project_specific_output_dir.is_dir()
            and any(project_specific_output_dir.iterdir())
        ):
            logger.info(
                "DocStringsSrc: pdoc content generated "
                "successfully in subdirectory %s.",
                project_specific_output_dir,
            )
            return str(project_specific_output_dir)

        single_html_file = pdoc_base_output_dir / f"{project_name}.html"
        if single_html_file.exists() and single_html_file.is_file():
            logger.info(
                "DocStringsSrc: pdoc content is a single HTML file: %s.",
                single_html_file,
            )
            return str(single_html_file)

        logger.warning(
            "DocStringsSrc: Expected pdoc content directory %s OR "
            "file %s not found or empty.",
            project_specific_output_dir,
            single_html_file,
        )
        return None

    @staticmethod
    def cleanup_folder(folder_or_list: Path | str | list[Path | str]) -> None:
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
                with contextlib.suppress(FileNotFoundError):
                    item_path.unlink()

    @staticmethod
    def git_clone(repo_url: str, clone_dir_path: Path) -> None:
        """Clone a git repository, trying 'main' then 'master'."""
        clone_dir_path_str = str(clone_dir_path)
        branches_to_try = ["main", "master"]
        last_error = None

        for branch_name in branches_to_try:
            logger.info(
                "Attempting to clone branch '%s' from %s into %s",
                branch_name,
                repo_url,
                clone_dir_path_str,
            )
            if clone_dir_path.exists():
                logger.debug(f"Cleaning up existing clone directory: {clone_dir_path}")
                shutil.rmtree(clone_dir_path)
            clone_dir_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                subprocess.run(  # noqa: S603
                    [
                        GIT_FULL_PATH,
                        "clone",
                        "--depth",
                        "1",
                        "--branch",
                        branch_name,
                        repo_url,
                        clone_dir_path_str,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                logger.info(
                    "Successfully cloned branch '%s' from %s.",
                    branch_name,
                    repo_url,
                )

            except subprocess.CalledProcessError as e:
                last_error = e
                logger.warning(
                    "Failed to clone branch '%s' for repository %s. Git stderr: %s",
                    branch_name,
                    repo_url,
                    e.stderr.strip() if e.stderr else "N/A",
                )
            except FileNotFoundError as e_fnf:
                logger.critical(
                    "Git command not found. Ensure git is installed and "
                    "in your system's PATH."
                )
                raise GitCloneFailedUnknownReasonError(
                    repo_url, branches_to_try
                ) from e_fnf
            else:
                return
        msg = (
            f"Could not clone repository {repo_url} from branches "
            f"{', '.join(branches_to_try)}."
        )
        logger.error(msg)
        if last_error:
            raise RuntimeError(msg) from last_error
        raise GitCloneFailedUnknownReasonError(repo_url, branches_to_try)

    def _define_run_paths(
        self,
        project_name: str,
    ) -> tuple[Path, Path, Path]:
        """Define and returns standard paths used in the run method."""
        cloned_repo_path = Path(project_name)

        final_docs_destination = self.docset_dir / project_name

        temp_output_dirname = f"tmp_pdoc_output_{project_name}"
        pdoc_operation_basedir = self.docset_dir / temp_output_dirname

        return cloned_repo_path, final_docs_destination, pdoc_operation_basedir

    def run(self, url: str, project_name: str) -> str | None:
        """Clone, generate docs, and move to final location."""
        cloned_repo_path: Path | None = None
        pdoc_operation_basedir: Path | None = None
        final_docs_path_str: str | None = None

        try:
            cloned_repo_path, final_docs_destination, pdoc_operation_basedir = (
                self._define_run_paths(project_name)
            )

            self.cleanup_folder(
                [cloned_repo_path, final_docs_destination, pdoc_operation_basedir]
            )
            self.git_clone(url, cloned_repo_path)

            logger.info("Calling generate_docs_from_folder for isolated build...")
            generation_outcome = self.generate_docs_from_folder(
                project_name,
                str(cloned_repo_path.parent.resolve()),
                str(pdoc_operation_basedir.resolve()),
            )

            if isinstance(generation_outcome, str):
                self._handle_successful_doc_move(
                    generation_outcome, final_docs_destination
                )
                final_docs_path_str = str(final_docs_destination.resolve())
            else:
                logger.error(
                    "Documentation generation failed for %s using isolated build.",
                    project_name,
                )
        except subprocess.CalledProcessError as cpe:
            self._log_subprocess_error(cpe, f"Run phase for {project_name}")
        except RuntimeError:
            logger.exception("Runtime error during run for %s", project_name)
        except OSError:
            logger.exception("OS error during run for %s", project_name)
            self._log_traceback()
        except (KeyboardInterrupt, SystemExit):
            logger.warning(
                "Operation interrupted or system exit called for %s.", project_name
            )
            raise
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

        return final_docs_path_str

    @staticmethod
    def _extract_missing_module_name(error_message: str) -> str | None:
        """Extract il nome del modulo da un messaggio di ModuleNotFoundError.

        Es. "No module named 'X'" -> "X"
        """
        match = re.search(r"No module named '([^']*)'", error_message)
        if match:
            return match.group(1)
        return None

    def _handle_successful_doc_move(
        self, generated_content_path_str: str, final_docs_destination: Path
    ) -> None:
        """Handle moving generated docs to their final destination."""
        logger.info(
            "Documentation generated by isolated build at: %s",
            generated_content_path_str,
        )
        generated_path_obj = Path(generated_content_path_str)

        if final_docs_destination.exists():
            self.cleanup_folder(final_docs_destination)
        final_docs_destination.mkdir(parents=True, exist_ok=True)

        if generated_path_obj.is_file():
            target_file_path = final_docs_destination / generated_path_obj.name
            shutil.move(str(generated_path_obj), str(target_file_path))
            logger.info("Single documentation file moved to: %s", target_file_path)
        elif generated_path_obj.is_dir():
            if final_docs_destination.is_dir() and not any(
                final_docs_destination.iterdir()
            ):
                final_docs_destination.rmdir()

            final_docs_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(generated_path_obj), str(final_docs_destination))
            logger.info("Documentation directory moved to: %s", final_docs_destination)
        else:
            logger.error(
                "DocStringsSrc: Validated pdoc output path '%s' is neither a file"
                " nor a directory. Cannot move.",
                generated_path_obj,
            )
            return

        logger.info("Documentation moved to final location: %s", final_docs_destination)

    @staticmethod
    def _log_subprocess_error(
        cpe: subprocess.CalledProcessError, context_msg: str
    ) -> None:
        """Log details of a CalledProcessError."""
        logger.error("%s: Subprocess execution failed: %s", context_msg, cpe.cmd)
        logger.error("%s: Exit Code: %s", context_msg, cpe.returncode)
        if cpe.stdout and cpe.stdout.strip():
            logger.debug("%s: Stdout:\n%s", context_msg, cpe.stdout.strip())
        if cpe.stderr and cpe.stderr.strip():
            logger.error("%s: Stderr:\n%s", context_msg, cpe.stderr.strip())


if __name__ == "__main__":
    P_URL = "https://github.com/psf/black"
    p_name = P_URL.rsplit("/", maxsplit=1)[-1]
    d_src = DocStringsSrc()
    d_src.run(P_URL, p_name)
