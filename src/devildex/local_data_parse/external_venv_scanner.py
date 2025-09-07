"""external venv scanner module."""

import importlib.resources
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from devildex.models import PackageDetails

HELPER_SCRIPT_FILENAME = "_external_scanner_script.py"

logger = logging.getLogger(__name__)


class ExternalVenvScanner:
    """Class that implements ExternalVenvScanner."""

    def __init__(self, python_executable_path: str) -> None:
        """Construct ExternalVenvScanner."""
        self.python_executable_path = Path(python_executable_path)

        self.script_content: Optional[str] = self._load_helper_script_content()

        if not self.python_executable_path.is_file():
            logger.warning(
                f"ExternalVenvScanner: python executable path given "
                f"'{self.python_executable_path}' doesn't seem to be a valid file."
            )
        if self.script_content is None:
            logger.error(
                "ExternalVenvScanner: script helper content not loaded "
                "durante initialization. "
                "Le scans fail."
            )

    def _execute_helper_script(
        self, temp_script_output_path: str
    ) -> Optional[subprocess.CompletedProcess]:
        """Execute the helper Python script in the target environment.

        Args:
            temp_script_output_path: Path to the temporary file where the script
                                     will write its JSON output.

        Returns:
            A subprocess.CompletedProcess object if execution finished
            successfully (even with errors),
            or None if a critical exception occurred during subprocess.run itself.

        """
        if not self.script_content:
            logger.error("Cannot execute helper script: script content not loaded.")
            return None

        command = [
            str(self.python_executable_path),
            "-c",
            self.script_content,
            temp_script_output_path,
        ]
        logger.debug(
            f"Executing command: {command[0]} -c <script_content> {command[3]}"
        )

        try:
            result = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                timeout=60,
            )
            if result.stdout:
                logger.debug(
                    "STDOUT (diagnostic) of helper script:\n%s", result.stdout.strip()
                )
            if result.stderr:
                logger.info("STDERR (log) of helper script:\n%s", result.stderr.strip())
        except subprocess.TimeoutExpired:
            logger.exception(
                "Timeout Expired during the execution of the helper script with '%s'.",
                self.python_executable_path,
            )
            return None
        except FileNotFoundError:  # Python executable itself not found at runtime
            logger.exception(
                "Python executable '%s' not found during the attempt "
                "to execute helper script.",
                self.python_executable_path,
            )
            return None
        except OSError:
            logger.exception(
                "OS error during execution of the helper script with '%s'",
                self.python_executable_path,
            )
            return None
        else:
            return result

    @staticmethod
    def _load_helper_script_content() -> Optional[str]:
        """Load the content of the helper script."""
        try:
            package = "devildex.local_data_parse"
            script_resource_path = (
                importlib.resources.files(package) / HELPER_SCRIPT_FILENAME
            )

            if not script_resource_path.is_file():
                logger.error(
                    f"Helper script '{HELPER_SCRIPT_FILENAME}' not found as file "
                    f"in {script_resource_path} using importlib.resources."
                )
                return None
            return script_resource_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.exception(
                f"Helper script '{HELPER_SCRIPT_FILENAME}' "
                "non trovato (FileNotFoundError)."
            )
            return None
        except (OSError, TypeError, UnicodeDecodeError):
            logger.exception(
                "Error during loading helper script " f"'{HELPER_SCRIPT_FILENAME}'"
            )
            return None

    @staticmethod
    def _parse_and_convert_scan_data(
        json_data_str: str, source_description: str
    ) -> Optional[list[PackageDetails]]:
        """Parse JSON string output from helper script and converts to PackageDetails.

        Args:
            json_data_str: The JSON string read from the script's output.
            source_description: A description of the source for logging.

        Returns:
            A list of PackageDetails objects, an empty list if no packages,
             or None on error.

        """
        try:
            data = json.loads(json_data_str)

            if isinstance(data, dict) and "error" in data:
                logger.error(
                    "The helper script reported an error in its JSON "
                    "output from %s: %s",
                    source_description,
                    data.get("error"),
                )
                if "traceback" in data:
                    logger.error(
                        "Traceback from helper script:\n%s", data.get("traceback")
                    )
                return None  # Script indicated an internal error

            if not isinstance(data, list):
                logger.error(
                    "Unexpected output format (not a JSON list of "
                    "packages or a known error JSON) "
                    "from %s.",
                    source_description,
                )
                logger.debug("Content (first 500 chars): %s...", json_data_str[:500])
                return None

            package_details_list: list[PackageDetails] = []
            for item in data:
                if not isinstance(item, dict):
                    logger.warning(
                        "Non-dictionary element found in JSON data from %s: %s",
                        source_description,
                        item,
                    )
                    continue
                try:
                    pkg = PackageDetails.from_dict(item)
                    package_details_list.append(pkg)
                except Exception as e_pkg:  # pylint: disable=broad-except
                    logger.warning(
                        "Error converting JSON package data from %s to "
                        "PackageDetails: %s. Error: %s",
                        source_description,
                        item,
                        e_pkg,
                    )

        except json.JSONDecodeError:
            logger.exception("Error decoding JSON output from %s.", source_description)
            logger.debug(
                "Non-parsable content (first 500 chars): %s...", json_data_str[:500]
            )
            return None
        else:
            return package_details_list

    def _read_and_process_output_file(
        self, output_file_path: Path
    ) -> Optional[list[PackageDetails]]:
        """Read the output file, parses JSON, and converts to PackageDetails."""
        if not output_file_path.is_file() or output_file_path.stat().st_size == 0:
            logger.error(
                "The temporary output file '%s' was not created or is empty "
                "by the helper script, although the script exited successfully.",
                output_file_path,
            )
            return []

        try:
            json_output_from_file = output_file_path.read_text(encoding="utf-8")
            if not json_output_from_file.strip():
                logger.info(
                    "No JSON content in the temporary output file '%s' "
                    "(No packages found or Venv empty?).",
                    output_file_path,
                )
                return []  # No packages or empty venv

            return self._parse_and_convert_scan_data(
                json_output_from_file, str(output_file_path)
            )
        except OSError:
            logger.exception(
                "Error reading temporary output file '%s'.", output_file_path
            )
            return None

    def scan_packages(self) -> Optional[list[PackageDetails]]:
        """Scan packages in the external venv."""
        if not self.script_content:
            logger.error("Helper script content not loaded. Cannot scan packages.")
            return None

        if not self.python_executable_path.is_file():
            logger.error(
                f"Unable to scan: specified python executable "
                f"'{self.python_executable_path}' doesn't exist or is not a file."
            )
            return None

        logger.info(
            "Initiating scan with '%s' and the helper script.",
            self.python_executable_path,
        )

        temp_output_file_path_str: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".json", prefix="devildex_scan_"
            ) as tmp_file_obj:
                temp_output_file_path_str = tmp_file_obj.name

            logger.debug(f"Temporary file for scan output: {temp_output_file_path_str}")

            process_result = self._execute_helper_script(temp_output_file_path_str)

            if process_result is None:  # Critical failure during script execution
                return None

            if process_result.returncode != 0:
                logger.error(
                    "Helper script exited with error code %s when run with '%s'. "
                    "See previous logs for script's stdout/stderr.",
                    process_result.returncode,
                    self.python_executable_path,
                )
                return None  # Script itself indicated failure via return code

            # Script executed with return code 0, now process its output file.
            output_file_path_obj = Path(temp_output_file_path_str)
            packages = self._read_and_process_output_file(output_file_path_obj)

            if packages is not None:
                logger.debug(
                    "Scan complete for %s. Found %d packages.",
                    self.python_executable_path,
                    len(packages),
                )
            return packages

        finally:
            if temp_output_file_path_str:
                try:
                    Path(temp_output_file_path_str).unlink(missing_ok=True)
                    logger.debug(
                        f"Cleaned up temporary output file: {temp_output_file_path_str}"
                    )
                except OSError as e_unlink:
                    logger.warning(
                        "Could not delete temporary output file '%s': %s",
                        temp_output_file_path_str,
                        e_unlink,
                    )


if __name__ == "__main__":
    
    test_exec_path = "/home/magowiz/venvs/tempenv-08109221402d/bin/python"

    if not Path(test_exec_path).is_file():
        logger.error(
            f"The test path '{test_exec_path}'It's not a valid file. Change the script."
        )
    else:
        scanner = ExternalVenvScanner(python_executable_path=test_exec_path)
        if scanner.script_content:
            logger.info("Content of script helper loaded con successfully!")
            logger.debug(f"Initial content: {scanner.script_content[:200]}...")
        else:
            logger.error("Failed il load del content of script helper.")

        logger.info("Trying to call scan_packages (simulation)...")
        packs = scanner.scan_packages()
        if packs is not None:
            logger.info(f"scan_packages (simulation) ha returned: {packs}")
        else:
            logger.error("scan_packages (simulation) ha returned None (error).")
