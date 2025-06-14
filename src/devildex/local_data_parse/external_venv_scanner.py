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
                f"ExternalVenvScanner: Il path dell'eseguibile Python given "
                f"'{self.python_executable_path}' non seem to be un file valido."
            )
        if self.script_content is None:
            logger.error(
                "ExternalVenvScanner: script helper content not loaded "
                "durante initialization. "
                "Le scans fail."
            )

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
                    f"Helper script '{HELPER_SCRIPT_FILENAME}' non trovato come file "
                    f"in {script_resource_path} tramite importlib.resources."
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
                "Error durante il caricamento dello script helper "
                f"'{HELPER_SCRIPT_FILENAME}'"
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
            "Simulating scan with "
            f"{self.python_executable_path} and the helper script."
        )

        temp_output_file_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".json", prefix="devildex_scan_"
            ) as tmp_file:
                temp_output_file_path = tmp_file.name
            logger.info(
                "Temporary file created for scan output: " f"{temp_output_file_path}"
            )
            command = [
                str(self.python_executable_path),
                "-c",
                self.script_content,
                temp_output_file_path,
            ]
            logger.debug(
                f"Executing command: {command[0]} -c <script_content> {command[3]}"
            )

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
                    "STDOUT (diagnostic) of script " f"helper:\n{result.stdout.strip()}"
                )
            if result.stderr:
                logger.info(f"STDERR (log) of script helper:\n{result.stderr.strip()}")
            if result.returncode != 0:
                return None

            if not temp_output_file_path:
                logger.error(
                    "Internal Error: temp_output_file_path is "
                    "None after subprocess execution."
                )
                return None

            output_file_path_obj = Path(temp_output_file_path)
            if (
                not output_file_path_obj.is_file()
                or output_file_path_obj.stat().st_size == 0
            ):
                logger.error(
                    f"The temporary output file '{temp_output_file_path}' It was not "
                    "created or is empty by the "
                    "helper script, although the exit code was 0."
                )

                return []

            json_output_from_file = output_file_path_obj.read_text(encoding="utf-8")

            if not json_output_from_file.strip():
                logger.info(
                    "No Json content in the temporary output file "
                    f"'{temp_output_file_path}'(No package found or Venv empty?)."
                )

                return []

            try:
                data = json.loads(json_output_from_file)

                if isinstance(data, dict) and "error" in data:
                    logger.error(
                        "The helper script reported an error in the Json file:"
                        f"{data.get('error')}"
                    )

                    if "traceback" in data:
                        logger.error(
                            f"Traceback from script helper:\n{data.get('traceback')}"
                        )
                    return None

                if not isinstance(data, list):
                    logger.error(
                        "Unexpected output (not a Json list of packets or an error json) "
                        f"from the temporary file '{temp_output_file_path}'."
                    )
                    logger.debug(
                        "File content (first 500 characters):"
                        f"{json_output_from_file[:500]}..."
                    )

                    return None

                package_details_list: list[PackageDetails] = []
                for item in data:
                    if not isinstance(item, dict):
                        logger.warning(
                            "Non-dictionary element found in the Json data from the"
                            f" file:{item}"
                        )

                        continue
                    try:
                        pkg = PackageDetails.from_dict(item)
                        package_details_list.append(pkg)
                    except Exception as e_pkg:  # pylint: disable=broad-except
                        logger.warning(
                            f"Error in converting the data of the Json package into "
                            f"PackageDetails:{item}. Error:{e_pkg}"
                        )

                logger.debug(
                    f"Scan complete for{self.python_executable_path}. "
                    f"Found{len(package_details_list)} packages reading from files."
                )

            except json.JSONDecodeError:
                logger.exception(
                    "Error in the Json Output decoding from the temporary file "
                    f"'{temp_output_file_path}'."
                )
                logger.debug(
                    "Content of the non-parsable file (first 500 characters):"
                    f"{json_output_from_file[:500]}..."
                )
                return None
            else:
                return package_details_list
        except subprocess.TimeoutExpired:
            logger.exception(
                "Timeout Expired during the execution of the External Script with '"
                f"{self.python_executable_path}'."
            )

            return None
        except FileNotFoundError:
            logger.exception(
                f"Executable python '{self.python_executable_path}'"
                " not found during the attempt to execute."
            )
            return None
        except (TypeError, ValueError, AttributeError):
            logger.exception(
                f"Unexpected Error during the execution of the external script with "
                f"'{self.python_executable_path}'"
            )
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
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
        packages = scanner.scan_packages()
        if packages is not None:
            logger.info(f"scan_packages (simulation) ha returned: {packages}")
        else:
            logger.error("scan_packages (simulation) ha returned None (error).")
