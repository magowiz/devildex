"""documentation orchestrator module."""

from pathlib import Path

from devildex.docstrings.docstrings_src import DocStringsSrc
from devildex.fetcher import PackageSourceFetcher
from devildex.info import PROJECT_ROOT
from devildex.models import PackageDetails
from devildex.readthedocs.readthedocs_api import \
    download_readthedocs_prebuilt_robust
from devildex.readthedocs.readthedocs_src import \
    download_readthedocs_source_and_build
from devildex.scanner.scanner import has_docstrings, is_sphinx_project


class Orchestrator:
    """Implement orchestrator class which detects doc type and perform right action."""

    def __init__(
        self,
        package_details: PackageDetails,
        base_output_dir=None,
    ):
        """Implement class constructor."""
        self.package_details = package_details
        self.detected_doc_type = None
        PDOC3_THEME_PATH = (
            PROJECT_ROOT / "src" / "devildex" / "theming" / "devildex_pdoc3_theme"
        )
        self.doc_strings = DocStringsSrc(template_dir=PDOC3_THEME_PATH)
        self.last_operation_result = None
        if base_output_dir:
            self.base_output_dir = Path(base_output_dir).resolve()
        else:
            self.base_output_dir = (PROJECT_ROOT / "docset").resolve()
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        self.doc_strings.docset_dir = self.base_output_dir
        self._effective_source_path = None

    def fetch_repo(self) -> bool:
        """
        Ensures that project sources are available, either from an initial path
        or by fetching them. Sets self._effective_source_path.

        Returns:
            bool: True if sources are now available at self._effective_source_path, False otherwise.
        """
        self._effective_source_path = None
        source_path_candidate: Path | None = None

        if self.package_details.initial_source_path:
            candidate = Path(self.package_details.initial_source_path)
            if candidate.exists() and candidate.is_dir():
                print(f"Orchestrator: Using provided initial_source_path: {candidate}")
                source_path_candidate = candidate.resolve()
            else:
                print(
                    f"Orchestrator WARNING: Provided initial_source_path '{candidate}' is not valid or does not exist."
                )

        if not source_path_candidate:
            print(
                f"Orchestrator: No valid initial_source_path. Attempting to fetch sources for {self.package_details.name} v{self.package_details.version}"
            )

            fetcher_storage_base = self.base_output_dir / "_fetched_project_sources"

            package_info_for_fetcher = {
                "name": self.package_details.name,
                "version": self.package_details.version,
                "project_urls": self.package_details.project_urls or {},
            }

            fetcher = PackageSourceFetcher(
                base_save_path=str(fetcher_storage_base),
                package_info_dict=package_info_for_fetcher,
            )
            try:
                fetch_successful, _is_master_branch, fetched_path_str = fetcher.fetch()

                if fetch_successful and fetched_path_str:
                    print(
                        f"Orchestrator: Fetch successful. Sources at: {fetched_path_str}"
                    )
                    source_path_candidate = Path(fetched_path_str).resolve()
                else:
                    print(
                        f"Orchestrator: Fetch failed for {self.package_details.name}. Fetcher returned: success={fetch_successful}, path={fetched_path_str}"
                    )
                    source_path_candidate = None
            except Exception as e:
                print(
                    f"Orchestrator: Exception during fetch for {self.package_details.name}: {e}"
                )
                source_path_candidate = None

        if (
            source_path_candidate
            and source_path_candidate.exists()
            and source_path_candidate.is_dir()
        ):
            self._effective_source_path = source_path_candidate
            print(
                f"Orchestrator: Effective source path set to: {self._effective_source_path}"
            )
            return True
        else:
            print(
                f"Orchestrator ERROR: No valid source path available (neither provided nor fetched). Evaluated path: {source_path_candidate}"
            )
            self._effective_source_path = None
            return False

    @property
    def _grabbers(self):
        """Property to dynamically build the grabbers configuration."""
        initial_path_str = (
            str(self.package_details.initial_source_path)
            if self.package_details.initial_source_path
            else None
        )
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
    def _interpret_tuple_res(value) -> str | None:
        if isinstance(value, tuple):
            return value[0] and value[1]
        return value

    def grab_build_doc(self) -> str | bool:
        """Grab and build documentation."""
        if self.detected_doc_type and self.detected_doc_type != "unknown":
            try:
                grabber_config = self._grabbers.get(self.detected_doc_type)
                method = grabber_config["function"]
                args = grabber_config["args"]
                res = method(**args)
                print(f" DETECTED DOC TYPE: {self.detected_doc_type}")
                print(f" RESULT FROM GRABBER: {res}")
                int_res = self._interpret_tuple_res(res)
                self.last_operation_result = int_res
                return int_res
            except KeyError:
                self.last_operation_result = False
        elif not self.detected_doc_type:
            self.last_operation_result = False
            print("no scan result, please call start_scan first")
        else:
            self.last_operation_result = False
            print("scan cannot detect any doc, unable to grab")
        return self.last_operation_result

    def start_scan(self):
        """Start the scanning process."""
        self.detected_doc_type = "unknown"
        if not self.fetch_repo():
            print(
                "Orchestrator: Failed to fetch or find repository sources. Scan cannot proceed."
            )
            self.detected_doc_type = "unknown"
            return
        if self._effective_source_path:
            scan_path_str = str(self._effective_source_path)
            print(f"Orchestrator: Scanning effective source path: {scan_path_str}")

            if is_sphinx_project(scan_path_str):
                self.detected_doc_type = "sphinx"
            elif has_docstrings(scan_path_str):  # Controlla questo come fallback
                self.detected_doc_type = "docstrings"

            if self.detected_doc_type == "unknown":
                print(
                    f"Orchestrator: Scan of '{scan_path_str}' did not identify a specific doc type (Sphinx, Docstrings)."
                )

            print(
                f"Orchestrator: Scan complete. Detected doc type from source files: '{self.detected_doc_type}' for path {self._effective_source_path}"
            )
        else:
            print(
                "Orchestrator ERROR: _effective_source_path is not set even after fetch_repo reported success. This should not happen."
            )
            self.detected_doc_type = "unknown"

    def get_detected_doc_type(self):
        """Get detected document type."""
        return self.detected_doc_type

    def get_last_operation_result(self):
        """Get last operation result."""
        return self.last_operation_result


if __name__ == "__main__":
    print("--- Orchestrator Usage Example ---")

    EXAMPLE_PROJECT_PATH_RTD = "/tmp/test_project_for_rtd"
    EXAMPLE_RTD_URL = "https://example-docs.readthedocs.io"

    EXAMPLE_PROJECT_PATH_LOCAL = "/tmp/test_project_local_scan"

    EXAMPLE_PROJECT_PATH_UNKNOWN = "/tmp/test_project_unknown"

    print(f"\n--- Scenario 1: Project with ReadTheDocs URL ({EXAMPLE_RTD_URL}) ---")
    orchestrator1 = Orchestrator(
        project_name="test_project_rtd",
        project_path=EXAMPLE_PROJECT_PATH_RTD,
        rtd_url=EXAMPLE_RTD_URL,
    )

    print("Starting scan...")
    orchestrator1.start_scan()
    print(f"Detected type: {orchestrator1.get_detected_doc_type()}")

    print("Starting grab/build documentation...")
    orchestrator1.grab_build_doc()
    print(f"Operation outcome: {orchestrator1.get_last_operation_result()}")

    print(
        "\n--- Scenario 2: Project without RTD URL (path: "
        f"{EXAMPLE_PROJECT_PATH_LOCAL}) ---"
    )
    orchestrator2 = Orchestrator(
        project_path=EXAMPLE_PROJECT_PATH_LOCAL,
        rtd_url=None,
        project_name="test_project_local",
    )

    print("Starting scan...")
    orchestrator2.start_scan()
    print(f"Detected type: {orchestrator2.get_detected_doc_type()}")

    print("Starting grab/build documentation...")
    orchestrator2.grab_build_doc()
    print(f"Operation outcome: {orchestrator2.get_last_operation_result()}")
    print(
        "\n--- Scenario 3: Project with no detectable documentation "
        f"({EXAMPLE_PROJECT_PATH_UNKNOWN}) ---"
    )
    orchestrator3 = Orchestrator(
        project_path=EXAMPLE_PROJECT_PATH_UNKNOWN, project_name="test_project_unknown"
    )

    print("Starting scan...")
    orchestrator3.start_scan()
    print(f"Detected type: {orchestrator3.get_detected_doc_type()}")

    print("Starting grab/build documentation...")
    orchestrator3.grab_build_doc()
    print(f"Operation outcome: {orchestrator3.get_last_operation_result()}")

    print("\n--- Scenario 4: Calling grab_build_doc() before start_scan() ---")
    orchestrator4 = Orchestrator(
        project_path="/tmp/another_project_no_scan",
        project_name="another_project_no_scan",
    )
    print("Attempting grab/build documentation without prior scan...")
    orchestrator4.grab_build_doc()
    print(f"Operation outcome: {orchestrator4.get_last_operation_result()}")

    print("\n--- End of Orchestrator Usage Example ---")
