"""docstrings pdoc3 module."""

import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from devildex.grabbers.abstract_grabber import AbstractGrabber
from devildex.orchestrator.context import BuildContext
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command,
    install_project_and_dependencies_in_venv,
)

logger = logging.getLogger(__name__)

INIT_FILENAME = "__init__.py"


@dataclass
class PDocContext:
    """Holds context for a pdoc build operation."""

    modules_to_document: list[str]
    pdoc_cwd: Path
    project_install_root: Path
    requirements_file: Path | None
    pdoc_command_output_dir: Path
    project_name_for_log: str





class Pdoc3Builder(AbstractGrabber):
    """Implement class that build documentation from docstrings."""

    def __init__(
        self, template_dir: Optional[Path] = None
    ) -> None:
        """Initialize Pdoc3Builder."""
        super().__init__()
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
                "Pdoc3Builder: No module specified for PDOC. "
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
                    "Pdoc3Builder: Validated docs path %s is "
                    "neither file nor dir for static copy.",
                    validated_docs_path,
                )
                return

            if destination_static_dir.exists() and not destination_static_dir.is_dir():
                logger.warning(
                    "Pdoc3Builder: Static destination %s exists but is not"
                    " a directory. Removing it.",
                    destination_static_dir,
                )
                destination_static_dir.unlink()

            destination_static_dir.mkdir(parents=True, exist_ok=True)

            shutil.copytree(
                source_static_dir, destination_static_dir, dirs_exist_ok=True
            )

            logger.info(
                "Pdoc3Builder: copied static files from the theme to %s",
                destination_static_dir,
            )



    @staticmethod
    def _cleanup_pdoc_output_on_failure(
        pdoc_command_output_dir: Path, project_name: str
    ) -> None:
        """Clean up pdoc output directories in case of a build/validation failure."""
        project_specific_output_dir = pdoc_command_output_dir / project_name
        if project_specific_output_dir.exists():
            logger.info(
                "Pdoc3Builder: Cleaning up pdoc project specific output directory %s.",
                project_specific_output_dir,
            )
            try:
                shutil.rmtree(project_specific_output_dir)
                if pdoc_command_output_dir.exists() and not any(
                    pdoc_command_output_dir.iterdir()
                ):
                    shutil.rmtree(pdoc_command_output_dir)
                    logger.info(
                        "Pdoc3Builder: Removed empty base pdoc output directory %s.",
                        pdoc_command_output_dir,
                    )
            except OSError:
                logger.exception(
                    "Pdoc3Builder: Error cleaning up pdoc output directory %s",
                    project_specific_output_dir,
                )
        elif pdoc_command_output_dir.exists():
            logger.info(
                "Pdoc3Builder: Cleaning up base pdoc output directory %s "
                "as project specific dir was not found.",
                pdoc_command_output_dir,
            )
            try:
                shutil.rmtree(pdoc_command_output_dir)
            except OSError:
                logger.exception(
                    "Pdoc3Builder: Error cleaning up base pdoc output directory %s",
                    pdoc_command_output_dir,
                )

    def generate_docset(self, source_path: Path, output_path: Path, context: BuildContext) -> bool:
        """Generate HTML documentation using PDOC in an isolated environment."""
        logger.info("\n--- Starting Isolated pdoc Build for %s ---", context.project_name)

        if not source_path.is_dir():
            logger.info(
                "Pdoc3Builder: The Specified Source Project Folder does not exist: %s",
                source_path,
            )
            logger.info(
                "Pdoc3Builder: Details - input_folder: '%s', project_name: '%s'",
                source_path.parent,
                context.project_name,
            )
            return False

        logger.info(
            "Pdoc3Builder: Project source root for pdoc: %s", source_path
        )
        logger.info(
            "Pdoc3Builder: Main package to document with pdoc: %s", context.project_name
        )

        modules_for_pdoc_command = [context.project_name]

        logger.info(
            "Pdoc3Builder: modules/packages to go to PDOC: %s",
            modules_for_pdoc_command,
        )

        pdoc_command_output_dir = output_path / context.project_name

        if pdoc_command_output_dir.exists():
            shutil.rmtree(pdoc_command_output_dir)
        pdoc_command_output_dir.mkdir(parents=True, exist_ok=True)

        requirements_file_to_install = None
        candidate_req_paths = [
            source_path / "requirements.txt",
            source_path / "dev-requirements.txt",
            source_path / "requirements-dev.txt",
            source_path / "docs" / "requirements.txt",
        ]
        for req_path_candidate in candidate_req_paths:
            if req_path_candidate.exists() and req_path_candidate.is_file():
                logger.info(
                    "Pdoc3Builder: Found requirements file for dependencies: %s",
                    req_path_candidate,
                )
                requirements_file_to_install = req_path_candidate
                break
        if not requirements_file_to_install:
            logger.info(
                "Pdoc3Builder: No general 'requirements.txt' found for %s "
                "in common locations. "
                "Will rely on project's setup (e.g., setup.py, pyproject.toml).",
                context.project_name,
            )

        build_successful = False
        try:
            with IsolatedVenvManager(project_name=f"pdoc_{context.project_name}") as i_venv:
                logger.info(
                    "Pdoc3Builder: Created temporary venv for pdoc3 at %s",
                    i_venv.venv_path,
                )
                base_deps_for_pdoc_and_build = ["pdoc3"]
                install_deps_success = install_project_and_dependencies_in_venv(
                    pip_executable=i_venv.pip_executable,
                    project_name=context.project_name,
                    project_root_for_install=source_path,
                    doc_requirements_path=requirements_file_to_install,
                    base_packages_to_install=base_deps_for_pdoc_and_build,
                )

                if not install_deps_success:
                    logger.error(
                        "Pdoc3Builder: CRITICAL: Failed to install pdoc3 "
                        "or project dependencies for %s in venv. Aborting pdoc3 build.",
                        context.project_name,
                    )
                    build_successful = False
                else:
                    pdoc_exec_context = PDocContext(
                        modules_to_document=modules_for_pdoc_command,
                        pdoc_cwd=source_path.parent,
                        project_install_root=source_path,
                        requirements_file=requirements_file_to_install,
                        pdoc_command_output_dir=pdoc_command_output_dir,
                        project_name_for_log=context.project_name,
                    )
                    pdoc_command = self._build_pdoc_command(
                        i_venv.python_executable,
                        pdoc_exec_context.modules_to_document,
                        pdoc_exec_context.pdoc_command_output_dir,
                    )
                    if not pdoc_command:
                        build_successful = False
                    else:
                        logger.info("Pdoc3Builder: Executing pdoc: %s", " ".join(pdoc_command))
                        logger.info("Pdoc3Builder: pdoc CWD: %s", pdoc_exec_context.pdoc_cwd)
                        stdout, stderr, return_code = execute_command(
                            pdoc_command,
                            f"pdoc HTML generation for {pdoc_exec_context.project_name_for_log}",
                            cwd=pdoc_exec_context.pdoc_cwd,
                        )

                        if return_code == 0:
                            logger.info(
                                "Pdoc3Builder: pdoc build for %s completed successfully.",
                                pdoc_exec_context.project_name_for_log,
                            )
                            build_successful = True
                        else:
                            logger.error(
                                "Pdoc3Builder: pdoc build for %s FAILED. Return code: %s",
                                pdoc_exec_context.project_name_for_log,
                                return_code,
                            )
                            logger.debug("pdoc stdout:\n%s", stdout)
                            logger.debug("pdoc stderr:\n%s", stderr)
                            build_successful = False
        except RuntimeError:
            logger.exception(
                "Pdoc3Builder: Critical error during isolated pdoc build setup for %s",
                context.project_name,
            )
        except (KeyboardInterrupt, SystemExit):
            logger.warning(
                "Pdoc3Builder: Isolated pdoc build for %s "
                "interrupted or system exit called.",
                context.project_name,
            )
            raise
        finally:
            logger.info("--- Finished Isolated pdoc Build for %s ---", context.project_name)

        if build_successful:
            validated_docs_path_str = None
            project_specific_output_dir = pdoc_command_output_dir / context.project_name
            if (
                project_specific_output_dir.exists()
                and project_specific_output_dir.is_dir()
                and any(project_specific_output_dir.iterdir())
            ):
                logger.info(
                    "Pdoc3Builder: pdoc content generated "
                    "successfully in subdirectory %s.",
                    project_specific_output_dir,
                )
                validated_docs_path_str = str(project_specific_output_dir)

            single_html_file = pdoc_command_output_dir / f"{context.project_name}.html"
            if single_html_file.exists() and single_html_file.is_file():
                logger.info(
                    "Pdoc3Builder: pdoc content is a single HTML file: %s.",
                    single_html_file,
                )
                validated_docs_path_str = str(single_html_file)

            if not validated_docs_path_str:
                logger.warning(
                    "Pdoc3Builder: Expected pdoc content directory %s OR "
                    "file %s not found or empty.",
                    project_specific_output_dir,
                    single_html_file,
                )

            if validated_docs_path_str:
                validated_docs_path = Path(validated_docs_path_str)
                self._copy_theme_static_files(validated_docs_path)
                return True

            logger.info(
                "Pdoc3Builder: Build reported success, "
                "but content validation failed for %s. "
                "Cleaning up temporary output.",
                context.project_name,
            )
        else:
            logger.info(
                "Pdoc3Builder: pdoc build failed for %s. "
                "Cleaning up temporary output.",
                context.project_name,
            )

        project_specific_output_dir = pdoc_command_output_dir / context.project_name
        if project_specific_output_dir.exists():
            logger.info(
                "Pdoc3Builder: Cleaning up pdoc project specific output directory %s.",
                project_specific_output_dir,
            )
            try:
                shutil.rmtree(project_specific_output_dir)
                if pdoc_command_output_dir.exists() and not any(
                    pdoc_command_output_dir.iterdir()
                ):
                    shutil.rmtree(pdoc_command_output_dir)
                    logger.info(
                        "Pdoc3Builder: Removed empty base pdoc output directory %s.",
                        pdoc_command_output_dir,
                    )
            except OSError:
                logger.exception(
                    "Pdoc3Builder: Error cleaning up pdoc output directory %s",
                    project_specific_output_dir,
                )
        elif pdoc_command_output_dir.exists():
            logger.info(
                "Pdoc3Builder: Cleaning up base pdoc output directory %s "
                "as project specific dir was not found.",
                pdoc_command_output_dir,
            )
            try:
                shutil.rmtree(pdoc_command_output_dir)
            except OSError:
                logger.exception(
                    "Pdoc3Builder: Error cleaning up base pdoc output directory %s",
                    pdoc_command_output_dir,
                )
        return False

    def can_handle(self, source_path: Path, context: BuildContext) -> bool:
        """Determine if the grabber can handle a given project."""
        # Check for a pyproject.toml or setup.py that mentions pdoc3
        pyproject_toml_path = source_path / "pyproject.toml"
        if pyproject_toml_path.is_file():
            try:
                content = pyproject_toml_path.read_text()
                if "pdoc3" in content:
                    logger.info(f"Pdoc3Builder: Found 'pdoc3' in pyproject.toml at {pyproject_toml_path}. Can handle.")
                    return True
            except Exception as e:
                logger.warning(f"Pdoc3Builder: Error reading pyproject.toml at {pyproject_toml_path}: {e}")

        setup_py_path = source_path / "setup.py"
        if setup_py_path.is_file():
            try:
                content = setup_py_path.read_text()
                if "pdoc3" in content:
                    logger.info(f"Pdoc3Builder: Found 'pdoc3' in setup.py at {setup_py_path}. Can handle.")
                    return True
            except Exception as e:
                logger.warning(f"Pdoc3Builder: Error reading setup.py at {setup_py_path}: {e}")

        # Check for a 'docs' directory containing pdoc3-specific files (e.g., a config file if pdoc3 had one)
        # For now, a simple check for a 'docs' directory might be sufficient if no specific pdoc3 config file exists.
        # This can be refined later.
        docs_dir = source_path / "docs"
        if docs_dir.is_dir():
            # More specific checks can be added here if pdoc3 has a common config file name
            logger.info(f"Pdoc3Builder: Found 'docs' directory at {docs_dir}. Can potentially handle.")
            return True

        logger.info(f"Pdoc3Builder: No clear indication of a pdoc3 project at {source_path}. Cannot handle.")
        return False







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
                    "Pdoc3Builder: removed links to ' %s' from %s",
                    reported_folder_path,
                    html_file,
                )
                current_content = content_after_link_removal

            content_after_empty_li_cleanup = empty_li_pattern.sub("", current_content)
            if content_after_empty_li_cleanup != current_content:
                logger.debug(
                    "Pdoc3Builder: Clean <li> <Code> </code> "
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
                    "Pdoc3Builder: clean <dt> <code> </code> </ dt> "
                    "<dd> ... </dd> empty from %s (relative to %s)",
                    html_file,
                    reported_folder_path,
                )
                current_content = content_after_empty_dt_dd_cleanup

            if current_content != original_content:
                html_file.write_text(current_content, encoding="utf-8")
                logger.info(
                    "Pdoc3Builder: modified HTML %s file for "
                    "cleaning relating to %s",
                    html_file,
                    reported_folder_path,
                )
        except OSError:
            logger.exception(
                "Pdoc3Builder: error during processing the HTML %s"
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
                "Pdoc3Builder: no path to be tried from the non-payable report."
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
                        "Pdoc3Builder: canceled non-packing folder from "
                        "the PDOC Output: %s",
                        folder_to_delete_in_pdoc_output,
                    )
                except OSError:
                    logger.exception(
                        "Pdoc3Builder: Error during the cancellation of the %s "
                        "folder from the PDOC output.",
                        folder_to_delete_in_pdoc_output,
                    )
            else:
                logger.debug(
                    "Pdoc3Builder: delete folder not found in the PDOC Output "
                    "(or is not a dir): %s",
                    folder_to_delete_in_pdoc_output,
                )
            logger.info(
                "Pdoc3Builder: attempt to removal links and cleaning for ' %s'"
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
            logger.info("Pdoc3Builder: deleted report files: %s", report_file_path)

        except OSError:
            logger.exception(
                "Pdoc3Builder: Error when deleting the Report %s file",
                report_file_path,
            )















































