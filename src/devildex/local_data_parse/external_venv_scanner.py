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
                "ExternalVenvScanner: Contenuto dello script helper non loaded "
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
                f"Impossibile scansionare: l'eseguibile Python specificato "
                f"'{self.python_executable_path}' non esiste o non è un file."
            )
            return None

        logger.info(
            "Simulazione scansione con "
            f"{self.python_executable_path} e script helper."
        )

        temp_output_file_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".json", prefix="devildex_scan_"
            ) as tmp_file:
                temp_output_file_path = tmp_file.name
            logger.info(
                "Creato file temporaneo per l'output della scansione: "
                f"{temp_output_file_path}"
            )
            command = [
                str(self.python_executable_path),
                "-c",
                self.script_content,
                temp_output_file_path,
            ]
            logger.debug(
                f"Esecuzione comando: {command[0]} -c <contenuto_script> {command[3]}"
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
                    "STDOUT (diagnostica) dello script "
                    f"helper:\n{result.stdout.strip()}"
                )
            if result.stderr:
                logger.info(
                    f"STDERR (log) dello script helper:\n{result.stderr.strip()}"
                )
            if result.returncode != 0:
                return None

            if not temp_output_file_path:
                logger.error(
                    "Errore interno: temp_output_file_path è "
                    "None dopo l'esecuzione del subprocess."
                )
                return None

            output_file_path_obj = Path(temp_output_file_path)
            if (
                not output_file_path_obj.is_file()
                or output_file_path_obj.stat().st_size == 0
            ):
                logger.error(
                    f"Il file di output temporaneo '{temp_output_file_path}' "
                    "non è stato creato o è vuoto dallo script"
                    " helper, nonostante l'exit code fosse 0."
                )
                return []

            json_output_from_file = output_file_path_obj.read_text(encoding="utf-8")

            if not json_output_from_file.strip():
                logger.info(
                    "Nessun contenuto JSON nel file di output temporaneo "
                    f"'{temp_output_file_path}' "
                    "(nessun pacchetto trovato o venv vuoto?)."
                )
                return []

            try:
                data = json.loads(json_output_from_file)

                if isinstance(data, dict) and "error" in data:
                    logger.error(
                        "Lo script helper ha riportato un errore "
                        f"nel file JSON: {data.get('error')}"
                    )
                    if "traceback" in data:
                        logger.error(
                            f"Traceback dallo script helper:\n{data.get('traceback')}"
                        )
                    return None

                if not isinstance(data, list):
                    logger.error(
                        "Output inatteso (non una lista JSON di pacchetti "
                        "né un JSON di errore) "
                        f"dal file temporaneo '{temp_output_file_path}'."
                    )
                    logger.debug(
                        "Contenuto del file (primi 500 caratteri):"
                        f" {json_output_from_file[:500]}..."
                    )
                    return None

                package_details_list: list[PackageDetails] = []
                for item in data:
                    if not isinstance(item, dict):
                        logger.warning(
                            "Elemento non dizionario trovato nei "
                            f"dati JSON dal file: {item}"
                        )
                        continue
                    try:
                        pkg = PackageDetails.from_dict(item)
                        package_details_list.append(pkg)
                    except Exception as e_pkg:  # pylint: disable=broad-except
                        logger.warning(
                            "Errore nel convertire i dati del pacchetto JSON"
                            f" in PackageDetails: {item}. "
                            f"Errore: {e_pkg}"
                        )

                logger.debug(
                    f"Scan completed per {self.python_executable_path}. "
                    f"Found {len(package_details_list)} pacchetti leggendo da file."
                )

            except json.JSONDecodeError:
                logger.exception(
                    "Error nel decoding output JSON dal file "
                    f"temporaneo '{temp_output_file_path}'."
                )
                logger.debug(
                    "Contenuto del file non parsable (primi 500 caratteri):"
                    f" {json_output_from_file[:500]}..."
                )
                return None
            else:
                return package_details_list
        except subprocess.TimeoutExpired:
            logger.exception(
                f"Timeout expired durante l'esecuzione dello external script "
                f"con '{self.python_executable_path}'."
            )
            return None
        except FileNotFoundError:
            logger.exception(
                f"Executable Python '{self.python_executable_path}' non trovato "
                "durante il tentativo di esecuzione."
            )
            return None
        except (TypeError, ValueError, AttributeError):
            logger.exception(
                f"unexpected Error durante l'esecuzione dello script esterno con "
                f"'{self.python_executable_path}'"
            )
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_exec_path = "/home/magowiz/venvs/tempenv-08109221402d/bin/python"

    if not Path(test_exec_path).is_file():
        logger.error(
            f"Il path di test '{test_exec_path}' non è un file valido. "
            "Modifica lo script."
        )
    else:
        scanner = ExternalVenvScanner(python_executable_path=test_exec_path)
        if scanner.script_content:
            logger.info("Content del script helper loaded con successo!")
            logger.debug(f"Initial content: {scanner.script_content[:200]}...")
        else:
            logger.error("Failed il load del content of script helper.")

        logger.info("Trying to call scan_packages (simulation)...")
        packages = scanner.scan_packages()
        if packages is not None:
            logger.info(f"scan_packages (simulation) ha returned: {packages}")
        else:
            logger.error("scan_packages (simulation) ha returned None (error).")
