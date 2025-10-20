"""documentation orchestrator module."""

import logging
from pathlib import Path
from typing import Optional

from devildex.database.models import PackageDetails
from devildex.fetcher import PackageSourceFetcher
from devildex.grabbers.mkdocs_builder import MkDocsBuilder
from devildex.grabbers.pdoc3_builder import Pdoc3Builder
from devildex.grabbers.pydoctor_builder import PydoctorBuilder
from devildex.grabbers.sphinx_builder import SphinxBuilder
from devildex.info import PROJECT_ROOT
from devildex.orchestrator.context import BuildContext
from devildex.scanner.scanner import (
    _find_python_package_root,
    has_docstrings,
    is_mkdocs_project,
    is_sphinx_project,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """Implement orchestrator class which detects doc type and perform right action."""

    def __init__(
        self,
        package_details: PackageDetails,
        base_output_dir: Optional[Path | str] = None,
    ) -> None:
        """Implement class constructor."""
        self.package_details = package_details
        self.detected_doc_type = None
        pdoc3_theme_path = (
            PROJECT_ROOT / "src" / "devildex" / "theming" / "devildex_pdoc3_theme"
        )
        self.pdoc3_builder = Pdoc3Builder(template_dir=pdoc3_theme_path)
        pydoctor_theme_path = (
            PROJECT_ROOT / "src" / "devildex" / "theming" / "devildex_pydoctor_theme"
        )
        self.pydoctor_builder = PydoctorBuilder(template_dir=pydoctor_theme_path)
        self.last_operation_result = None
        self.sphinx_doc_path = None
        if base_output_dir:
            self.base_output_dir = Path(base_output_dir).resolve()
        else:
            self.base_output_dir = (PROJECT_ROOT / "docset").resolve()
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        self._effective_source_path = None

    def _fetch_repo_fetch(
        self, fetcher_storage_base: object, package_info_for_fetcher: dict
    ) -> Path | None:
        fetcher = PackageSourceFetcher(
            base_save_path=str(fetcher_storage_base),
            package_info_dict=package_info_for_fetcher,
        )
        try:
            fetch_successful, _is_master_branch, fetched_path_str = fetcher.fetch()

            if fetch_successful and fetched_path_str:
                logger.info(
                    f"Orchestrator: Fetch successful. Sources at: {fetched_path_str}"
                )
                source_path_candidate = Path(fetched_path_str).resolve()
            else:
                logger.error(
                    f"Orchestrator: Fetch failed for {self.package_details.name}."
                    f" Fetcher returned: success={fetch_successful}, "
                    f"path={fetched_path_str}"
                )
                source_path_candidate = None
        except (OSError, RuntimeError):
            logger.exception(
                f"Orchestrator: Exception during fetch for {self.package_details.name}"
            )
            source_path_candidate = None
        return source_path_candidate

    def fetch_repo(self) -> bool:
        """Fetch the repository sources."""
        logger.debug(f"Orchestrator.fetch_repo called for {self.package_details.name}")
        """Ensure that project sources are available, either from an initial path.

        or by fetching them. Sets self._effective_source_path.

        Returns:
            bool: True if sources are now available at
                self._effective_source_path, False otherwise.

        """
        self._effective_source_path = None
        source_path_candidate: Path | None = None

        if self.package_details.initial_source_path:
            candidate = Path(self.package_details.initial_source_path)
            if candidate.exists() and candidate.is_dir():
                logger.debug(
                    "Orchestrator: Using provided initial_source_path:" f" {candidate}"
                )
                source_path_candidate = candidate.resolve()
            else:
                logger.warning(
                    "Orchestrator WARNING: Provided "
                    f"initial_source_path '{candidate}' is not valid or does not exist."
                )

        if not source_path_candidate:
            logger.error(
                "Orchestrator: No valid initial_source_path. "
                "Attempting to fetch sources for "
                f"{self.package_details.name} v{self.package_details.version}"
            )

            fetcher_storage_base = self.base_output_dir / "_fetched_project_sources"

            package_info_for_fetcher = {
                "name": self.package_details.name,
                "version": self.package_details.version,
                "project_urls": self.package_details.project_urls or {},
            }

            source_path_candidate = self._fetch_repo_fetch(
                fetcher_storage_base, package_info_for_fetcher
            )
            logger.debug(f"_fetch_repo_fetch() returned: {source_path_candidate}")

        if (
            source_path_candidate
            and source_path_candidate.exists()
            and source_path_candidate.is_dir()
        ):
            self._effective_source_path = source_path_candidate
            logger.debug(
                "Orchestrator: Effective source path set to: "
                f"{self._effective_source_path}"
            )
            logger.debug(
                "Orchestrator.fetch_repo returning True. Effective path:"
                f" {self._effective_source_path}"
            )
            return True
        else:
            logger.error(
                "Orchestrator ERROR: No valid source path available "
                "(neither provided nor fetched). "
                f"Evaluated path: {source_path_candidate}"
            )
            self._effective_source_path = None
            logger.debug("Orchestrator.fetch_repo returning False.")
            return False

    @property
    def _grabbers(self) -> dict:
        """Property to dynamically build the grabbers' configuration."""
        return {
            "sphinx": {
                "builder": SphinxBuilder(),
                "context_args": {
                    "project_name": self.package_details.name,
                    "project_version": self.package_details.version,
                    "base_output_dir": self.base_output_dir,
                    "source_root": self._effective_source_path,
                    "vcs_url": self.package_details.vcs_url,
                    "project_slug": self.package_details.name,
                    "version_identifier": self.package_details.version or "main",
                    "project_root_for_install": self._effective_source_path,
                    "project_url": self.package_details.vcs_url,
                },
            },
            "mkdocs": {
                "builder": MkDocsBuilder(),
                "context_args": {
                    "project_name": self.package_details.name,
                    "project_version": self.package_details.version,
                    "base_output_dir": self.base_output_dir,
                    "source_root": self._effective_source_path,
                    "project_slug": self.package_details.name,
                    "version_identifier": self.package_details.version or "main",
                    "project_root_for_install": self._effective_source_path,
                },
            },
            "pydoctor": {
                "builder": self.pydoctor_builder,
                "context_args": {
                    "project_name": self.package_details.name,
                    "project_version": self.package_details.version,
                    "base_output_dir": self.base_output_dir,
                    "source_root": self._effective_source_path,
                    "vcs_url": self.package_details.vcs_url,
                    "project_slug": self.package_details.name,
                    "version_identifier": self.package_details.version or "main",
                    "project_root_for_install": self._effective_source_path,
                    "project_url": self.package_details.vcs_url,
                },
            },
            "pdoc3": {
                "builder": self.pdoc3_builder,
                "context_args": {
                    "project_name": self.package_details.name,
                    "project_version": self.package_details.version,
                    "base_output_dir": self.base_output_dir,
                    "source_root": self._effective_source_path,
                    "vcs_url": self.package_details.vcs_url,
                    "project_slug": self.package_details.name,
                    "version_identifier": self.package_details.version or "main",
                    "project_root_for_install": self._effective_source_path,
                    "project_url": self.package_details.vcs_url,
                },
            },
            "docstrings": {
                "function": self._generate_docstrings_with_fallback,
                "args": {
                    "context": BuildContext(
                        project_name=self.package_details.name,
                        project_version=self.package_details.version,
                        base_output_dir=self.base_output_dir,
                        source_root=Path(self._get_docstrings_input_folder()),
                        vcs_url=self.package_details.vcs_url,
                    )
                },
            },
        }

    def grab_build_doc(self) -> str | bool:
        """Grab and build documentation."""
        if self.detected_doc_type and self.detected_doc_type != "unknown":
            grabber_config = self._grabbers.get(self.detected_doc_type)
            if grabber_config:
                try:
                    if "builder" in grabber_config:
                        builder = grabber_config["builder"]
                        context_args = grabber_config["context_args"]
                        build_context = BuildContext(**context_args)
                        source_path = self._effective_source_path
                        if self.detected_doc_type == "sphinx":
                            source_path = Path(self.sphinx_doc_path)
                        res = builder.generate_docset(
                            source_path=source_path,
                            output_path=self.base_output_dir,
                            context=build_context,
                        )
                    else:
                        method = grabber_config["function"]
                        args = grabber_config["args"]
                        res = method(**args)

                    logger.info(f" DETECTED DOC TYPE: {self.detected_doc_type}")
                    logger.info(f" RESULT FROM GRABBER: {res}")
                    self.last_operation_result = res
                except Exception:
                    logger.exception(
                        "Orchestrator: Exception during grab_build_doc for"
                        f" {self.detected_doc_type}"
                    )
                    self.last_operation_result = False
                else:
                    return res
            else:
                self.last_operation_result = False
                logger.error(
                    f"Orchestrator: No grabber configuration found for type:"
                    f" {self.detected_doc_type}"
                )
        elif not self.detected_doc_type:
            self.last_operation_result = False
            logger.error("no scan result, please call start_scan first")
        else:
            self.last_operation_result = False
            logger.error("scan cannot detect any doc, unable to grab")
        return self.last_operation_result

    def _get_docstrings_input_folder(self) -> str:
        """Determine the correct input folder for docstrings generation.

        It tries to find the Python package root within the effective source path.
        """
        if not self._effective_source_path:
            logger.error(
                "Orchestrator: _effective_source_path is not set, "
                "cannot determine docstrings input folder."
            )
            return ""

        python_package_root = _find_python_package_root(self._effective_source_path)

        if python_package_root:
            logger.info(
                "Orchestrator: Found Python package root for docstrings: "
                f"{python_package_root}"
            )
            return str(python_package_root)
        else:
            logger.warning(
                "Orchestrator: Could not find a specific Python package root. "
                "Falling back to effective source path for docstrings: "
                f"{self._effective_source_path}"
            )
            return str(self._effective_source_path)

    def _generate_docstrings_with_fallback(self, context: BuildContext) -> str | bool:
        logger.info("Orchestrator: Attempting pdoc3 generation...")
        pdoc3_result = self.pdoc3_builder.generate_docset(
            source_path=Path(self._get_docstrings_input_folder()),
            output_path=self.base_output_dir,
            context=context,
        )

        if pdoc3_result:
            logger.info("Orchestrator: pdoc3 generation successful.")
            return str(self.base_output_dir / context.project_name)
        else:
            logger.warning(
                "Orchestrator: pdoc3 generation failed. "
                "Attempting Pydoctor generation..."
            )
            # For pydoctor, we need to pass source_path and output_path explicitly
            source_path_for_pydoctor = Path(self._get_docstrings_input_folder())
            output_path_for_pydoctor = self.base_output_dir
            pydoctor_result = self.pydoctor_builder.generate_docset(
                source_path=source_path_for_pydoctor,
                output_path=output_path_for_pydoctor,
                context=context,
            )
            if pydoctor_result:
                logger.info("Orchestrator: Pydoctor generation successful.")
                return str(self.base_output_dir / context.project_name)
            else:
                logger.error("Orchestrator: Pydoctor generation also failed.")
                return False

    def start_scan(self) -> None:
        """Start the scanning process."""
        logger.debug(f"Orchestrator.start_scan called for {self.package_details.name}")
        """Start the scanning process."""
        self.detected_doc_type = "unknown"
        if not self.fetch_repo():
            logger.debug(
                "Orchestrator: Failed to fetch or find repository sources."
                " Scan cannot proceed."
            )
            self.detected_doc_type = "unknown"
            logger.debug("Orchestrator.start_scan returning due to failed fetch_repo.")
            return
        if self._effective_source_path:
            scan_path_str = str(self._effective_source_path)
            logger.debug(
                "Orchestrator: Scanning effective source path: " f"{scan_path_str}"
            )

            sphinx_path = is_sphinx_project(scan_path_str)
            logger.debug(
                f"is_sphinx_project('{scan_path_str}') returned: {sphinx_path}"
            )
            if sphinx_path:
                self.detected_doc_type = "sphinx"
                self.sphinx_doc_path = sphinx_path
            elif is_mkdocs_project(scan_path_str):
                self.detected_doc_type = "mkdocs"
                logger.debug(f"is_mkdocs_project('{scan_path_str}') returned True.")
            elif has_docstrings(scan_path_str):
                self.detected_doc_type = "docstrings"
                logger.debug(f"has_docstrings('{scan_path_str}') returned True.")

            if self.detected_doc_type == "unknown":
                logger.error(
                    f"Orchestrator: Scan of '{scan_path_str}' did not identify"
                    " a specific doc type (Sphinx, Docstrings)."
                )

            logger.debug(
                "Orchestrator: Scan complete. Detected doc type"
                f" from source files: '{self.detected_doc_type}' "
                f"for path {self._effective_source_path}"
            )
        else:
            logger.error(
                "Orchestrator ERROR: _effective_source_path is not set even after "
                "fetch_repo reported success. This should not happen."
            )
            self.detected_doc_type = "unknown"
            logger.debug("Orchestrator.start_scan _effective_source_path is None.")

    def get_detected_doc_type(self) -> str:
        """Get detected document type."""
        return self.detected_doc_type

    def get_last_operation_result(self) -> str | bool:
        """Get last operation result."""
        return self.last_operation_result
