"""external venv scanner module."""
import importlib.resources
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from devildex.models import PackageDetails

HELPER_SCRIPT_FILENAME = '_external_scanner_script.py'

logger = logging.getLogger(__name__)

class ExternalVenvScanner:
    """Class that implements ExternalVenvScanner."""

    def __init__(self, python_executable_path: str) -> None:
        """Construct ExternalVenvScanner."""
        self.python_executable_path = Path(
            python_executable_path
        )

        self.script_content: Optional[str] = self._load_helper_script_content()


        if not self.python_executable_path.is_file():
            logger.warning(
                f"ExternalVenvScanner: Il path dell'eseguibile Python fornito "
                f"'{self.python_executable_path}' non sembra essere un file valido."
            )
        if self.script_content is None:
            logger.error(
                "ExternalVenvScanner: Contenuto dello script helper non loaded "
                "durante initialization. "
                "Le scans fail."
            )
    @staticmethod
    def _load_helper_script_content(
    ) -> Optional[str]:
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
                "Errore durante il caricamento dello script helper "
                f"'{HELPER_SCRIPT_FILENAME}'"
            )
            return None

    def scan_packages(self) -> Optional[list[PackageDetails]]:
        """Scan packages in the external venv."""
        if not self.script_content: # Già corretto
            logger.error("Helper script content not loaded. Cannot scan packages.")
            return None

        if not self.python_executable_path.is_file():
            logger.error(
                f"Impossibile scansionare: l'eseguibile Python specificato "
                f"'{self.python_executable_path}' non esiste o non è un file."
            )
            return None

        logger.info("Simulazione scansione con "
                    f"{self.python_executable_path} e script helper.")

        command = [
            str(self.python_executable_path),
            "-c",
            self.script_content,
        ]
        logger.debug(f"Esecuzione comando: {command[0]} -c <contenuto_script>")
        try:
            result = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                timeout=60,
            )

            if result.returncode != 0:
                logger.error(
                    f"Lo script external executed con '{self.python_executable_path}' "
                    f"è terminated con error (codice {result.returncode})."
                )
                logger.error(f"STDERR dello script external:\n{result.stderr}")
                if result.stdout:
                    logger.error(
                        "STDOUT dello script esterno (in caso di errore):\n"
                        f"{result.stdout}"
                    )
                return None
            stdout_output = result.stdout.strip()
            if not stdout_output:
                logger.info(
                    "Nessun output STDOUT (nessun pacchetto trovato o venv vuoto?) "
                    f"dal venv esterno ({self.python_executable_path})."
                )
                return []
            try:
                data = json.loads(stdout_output)

                if not isinstance(data, list):
                    logger.error(
                        "Output inatteso (non una lista JSON) dallo "
                        "script esterno nel venv "
                        f"({self.python_executable_path})."
                    )
                    logger.debug(
                        "Output ricevuto (primi 500 caratteri): "
                        f"{stdout_output[:500]}..."
                    )
                    return None
                package_details_list: list[
                    PackageDetails
                ] = []
                for item in data:
                    if not isinstance(item, dict):
                        logger.warning(
                            f"Element non dictionary trovato nei dati JSON: {item}"
                        )
                        continue

                    try:
                        pkg = PackageDetails.from_dict(item)
                        package_details_list.append(pkg)
                    except Exception as e:  # pylint: disable=broad-except
                        logger.warning(
                            "Errore nel convertire i dati del pacchetto JSON"
                            f" in PackageDetails: {item}. "
                            f"Errore: {e}"
                        )

                logger.debug(
                    f"Scan completed per {self.python_executable_path}. "
                    f"Found {len(package_details_list)} pacchetti."
                )


            except json.JSONDecodeError:
                logger.exception(
                    "Errore nel decoding output JSON da stdout "
                    "dello script esterno "
                    f"({self.python_executable_path})."
                )
                logger.debug(
                    "Output STDOUT non parsabile (primi 500 caratteri):"
                    f" {stdout_output[:500]}..."
                )
                return None
            else:
                return package_details_list

        except subprocess.TimeoutExpired:
            logger.exception(
                f"Timeout scaduto durante l'esecuzione dello external script "
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
        logger.error(f"Il percorso di test '{test_exec_path}' non è un file valido. "
                     "Modifica lo script.")
    else:
        scanner = ExternalVenvScanner(python_executable_path=test_exec_path)
        if scanner.script_content:
            logger.info("Contenuto dello script helper loaded con successo!")
            logger.debug(f"Inizio content: {scanner.script_content[:200]}...")
        else:
            logger.error("Failed il caricamento del content of script helper.")

        logger.info("Tentativo di call scan_packages (simulazione)...")
        packages = scanner.scan_packages()
        if packages is not None:
            logger.info(f"scan_packages (simulation) ha restituito: {packages}")
        else:
            logger.error("scan_packages (simulation) ha returned None (error).")
