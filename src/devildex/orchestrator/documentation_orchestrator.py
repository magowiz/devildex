"""documentation orchestrator module."""

from pathlib import Path

from devildex.docstrings.docstrings_src import DocStringsSrc
from devildex.info import PROJECT_ROOT
from devildex.readthedocs.readthedocs_api import download_readthedocs_prebuilt_robust
from devildex.readthedocs.readthedocs_src import download_readthedocs_source_and_build
from devildex.scanner.scanner import has_docstrings, is_sphinx_project


class Orchestrator:
    """Implement orchestrator class which detects doc type and perform right action."""

    def __init__(
        self,
        project_name,
        project_path,
        project_url=None,
        rtd_url=None,
        base_output_dir=None,
    ):
        """Implement class constructor."""
        self.detected_doc_type = None
        self.project_name = project_name
        self.project_path = project_path
        self.project_url = project_url
        self.rtd_url = rtd_url
        self.doc_strings = DocStringsSrc()
        self.last_operation_result = None
        if base_output_dir:
            self.base_output_dir = Path(base_output_dir).resolve()
        else:
            self.base_output_dir = (PROJECT_ROOT / "docset").resolve()
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _grabbers(self):
        """Property to dynamically build the grabbers configuration."""
        return {
            "sphinx": {
                "function": download_readthedocs_source_and_build,
                "args": {
                    "project_url": self.project_url,
                    "project_name": self.project_name,
                    "output_dir": str(self.base_output_dir),
                },
            },
            "readthedocs": {
                "function": download_readthedocs_prebuilt_robust,
                "args": {
                    "rtd_url": self.rtd_url,
                    "project_name": self.project_name,
                    "download_folder": str(self.base_output_dir),
                },
            },
            "docstrings": {
                "function": self.doc_strings.generate_docs_from_folder,
                "args": {
                    "input_folder": self.project_path,
                    "project_name": self.project_name,
                    "output_folder": self.base_output_dir,
                },
            },
        }

    @staticmethod
    def _interpret_tuple_res(value):
        if isinstance(value, tuple):
            return value[0] and value[1]
        return value

    def grab_build_doc(self):
        """Grab and build documentation."""
        if self.detected_doc_type and self.detected_doc_type != "unknown":
            try:
                method = self._grabbers.get(self.detected_doc_type)["function"]
                args = self._grabbers.get(self.detected_doc_type)["args"]
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
        if is_sphinx_project(self.project_path):
            self.detected_doc_type = "sphinx"
        elif self.rtd_url:
            self.detected_doc_type = "readthedocs"
        elif has_docstrings(self.project_path):
            self.detected_doc_type = "docstrings"
        else:
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
