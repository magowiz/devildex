"""documentation orchestrator module."""

import logging
from pathlib import Path
from typing import Optional

from devildex.database.models import PackageDetails
from devildex.docstrings.docstrings_src import DocStringsSrc
from devildex.fetcher import PackageSourceFetcher
from devildex.info import PROJECT_ROOT
from devildex.mkdocs.mkdocs_src import process_mkdocs_source_and_build
from devildex.readthedocs.readthedocs_api import download_readthedocs_prebuilt_robust
from devildex.readthedocs.readthedocs_src import download_readthedocs_source_and_build
from devildex.scanner.scanner import (
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
        self.doc_strings = DocStringsSrc(template_dir=pdoc3_theme_path)
        self.last_operation_result = None
        if base_output_dir:
            self.base_output_dir = Path(base_output_dir).resolve()
        else:
            self.base_output_dir = (PROJECT_ROOT / "docset").resolve()
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        self.doc_strings.docset_dir = self.base_output_dir
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
                logger.info(
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

        if (
            source_path_candidate
            and source_path_candidate.exists()
            and source_path_candidate.is_dir()
        ):
            self._effective_source_path = source_path_candidate
            logger.info(
                "Orchestrator: Effective source path set to: "
                f"{self._effective_source_path}"
            )
            return True
        else:
            logger.error(
                "Orchestrator ERROR: No valid source path available "
                "(neither provided nor fetched). "
                f"Evaluated path: {source_path_candidate}"
            )
            self._effective_source_path = None
            return False

    @property
    def _grabbers(self) -> dict:
        """Property to dynamically build the grabbers' configuration."""
        effective_source_path_str = (
            str(self._effective_source_path) if self._effective_source_path else None
        )

        existing_clone_path_for_sphinx: Path | None = None
        if (
            self._effective_source_path
            and self._effective_source_path.exists()
            and self._effective_source_path.is_dir()
        ):
            existing_clone_path_for_sphinx = self._effective_source_path

        return {
            "sphinx": {
                "function": download_readthedocs_source_and_build,
                "args": {
                    "project_url": self.package_details.vcs_url,
                    "project_name": self.package_details.name,
                    "output_dir": self.base_output_dir,
                    "clone_base_dir_override": self.base_output_dir / "temp_clones",
                    "existing_clone_path": existing_clone_path_for_sphinx,
                },
            },
            "mkdocs": {
                "function": process_mkdocs_source_and_build,
                "args": {
                    "source_project_path": effective_source_path_str,
                    "project_slug": self.package_details.name,
                    "version_identifier": self.package_details.version or "main",
                    "base_output_dir": self.base_output_dir,
                },
            },
            "readthedocs": {
                "function": download_readthedocs_prebuilt_robust,
                "args": {
                    "project_name": self.package_details.name,
                    "download_folder": str(self.base_output_dir),
                },
            },
            "docstrings": {
                "function": self.doc_strings.generate_docs_from_folder,
                "args": {
                    "input_folder": effective_source_path_str,
                    "project_name": self.package_details.name,
                    "output_folder": self.base_output_dir,
                },
            },
        }

    @staticmethod
    def _interpret_tuple_res(value: tuple[str, bool] | str) -> str | bool | None:
        if isinstance(value, tuple):
            return value[0] if value[1] else False
        return value

    def grab_build_doc(self) -> str | bool:
        """Grab and build documentation."""
        if self.detected_doc_type and self.detected_doc_type != "unknown":
            grabber_config = self._grabbers.get(self.detected_doc_type)
            if grabber_config:
                try:
                    method = grabber_config["function"]
                    args = grabber_config["args"]
                    res = method(**args)
                    logger.info(f" DETECTED DOC TYPE: {self.detected_doc_type}")
                    logger.info(f" RESULT FROM GRABBER: {res}")
                    int_res = self._interpret_tuple_res(res)
                    self.last_operation_result = int_res
                except Exception:
                    self.last_operation_result = False
                else:
                    return int_res
            else:
                self.last_operation_result = False
                logger.error(
                    f"Orchestrator: No grabber configuration found for type: {self.detected_doc_type}"
                )
        elif not self.detected_doc_type:
            self.last_operation_result = False
            logger.error("no scan result, please call start_scan first")
        else:
            self.last_operation_result = False
            logger.error("scan cannot detect any doc, unable to grab")
        return self.last_operation_result

    def start_scan(self) -> None:
        """Start the scanning process."""
        self.detected_doc_type = "unknown"
        if not self.fetch_repo():
            logger.error(
                "Orchestrator: Failed to fetch or find repository sources."
                " Scan cannot proceed."
            )
            self.detected_doc_type = "unknown"
            return
        if self._effective_source_path:
            scan_path_str = str(self._effective_source_path)
            logger.info(
                "Orchestrator: Scanning effective source path: " f"{scan_path_str}"
            )

            if is_sphinx_project(scan_path_str):
                self.detected_doc_type = "sphinx"
            elif is_mkdocs_project(scan_path_str):
                self.detected_doc_type = "mkdocs"
            elif has_docstrings(scan_path_str):
                self.detected_doc_type = "docstrings"

            if self.detected_doc_type == "unknown":
                logger.error(
                    f"Orchestrator: Scan of '{scan_path_str}' did not identify"
                    " a specific doc type (Sphinx, Docstrings)."
                )

            logger.info(
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

    def get_detected_doc_type(self) -> str:
        """Get detected document type."""
        return self.detected_doc_type

    def get_last_operation_result(self) -> str | bool:
        """Get last operation result."""
        return self.last_operation_result
