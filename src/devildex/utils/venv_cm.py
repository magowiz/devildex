import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
import logging  # È una buona idea aggiungere un po' di logging

logger = logging.getLogger(__name__)  # O un logger specifico per DevilDex


class IsolatedVenvManager:
    """
    A context manager to create and manage a temporary isolated Python virtual environment.
    """

    def __init__(self, project_name: str, base_temp_dir: Path | None = None):
        self.project_name = project_name
        self.base_temp_dir = base_temp_dir or Path(tempfile.gettempdir())
        self.venv_path: Path | None = None
        self.python_executable: str | None = None
        self.pip_executable: str | None = None

    def _create_venv(self):
        """Creates the virtual environment."""
        # Creare una sottocartella unica per questo venv
        # Usare tempfile.mkdtemp per una directory temporanea sicura

        self.venv_path = Path(
            tempfile.mkdtemp(
                prefix=f"devildex_venv_{self.project_name}_", dir=self.base_temp_dir
            )
        )
        logger.info(
            f"Creating temporary venv for '{self.project_name}' at: {self.venv_path}"
        )
        print(f"DEBUG VENV_CM: Attempting to create venv at: {self.venv_path}")

        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(self.venv_path)],
                check=True,
                capture_output=True,
                text=True,
            )

            # Determina i percorsi degli eseguibili nel venv
            # In Windows, gli eseguibili sono in venv_path/Scripts
            # In Unix/macOS, sono in venv_path/bin
            bin_dir = self.venv_path / ("Scripts" if sys.platform == "win32" else "bin")
            self.python_executable = str(
                bin_dir / ("python.exe" if sys.platform == "win32" else "python")
            )
            self.pip_executable = str(
                bin_dir / ("pip.exe" if sys.platform == "win32" else "pip")
            )
            print(
                f"DEBUG VENV_CM: VENV CREATED. Python executable: {self.python_executable}"
            )
            print(f"DEBUG VENV_CM: VENV CREATED. Pip executable: {self.pip_executable}")
            print(
                f"DEBUG VENV_CM: VENV CREATED. Does python exist? {Path(self.python_executable).exists()}"
            )
            print(
                f"DEBUG VENV_CM: VENV CREATED. Does pip exist? {Path(self.pip_executable).exists()}"
            )

            logger.info(f"Venv for '{self.project_name}' created successfully.")
            logger.info(f"  Python executable: {self.python_executable}")
            logger.info(f"  Pip executable: {self.pip_executable}")

            # Opzionale: aggiornare pip alla versione più recente nel venv
            self._upgrade_pip()

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create venv for '{self.project_name}': {e.stderr}")
            self._cleanup()  # Pulisci se la creazione fallisce
            raise
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during venv creation for '{self.project_name}': {e}"
            )
            self._cleanup()
            raise

    def _upgrade_pip(self):
        """Upgrades pip within the created virtual environment."""
        if not self.pip_executable:
            logger.warning("Pip executable not set, cannot upgrade pip.")
            return
        try:
            logger.info(f"Upgrading pip in venv: {self.venv_path}")
            # Usare python -m pip per assicurarsi di usare il pip del venv
            subprocess.run(
                [self.python_executable, "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
                cwd=self.venv_path,
            )
            logger.info("Pip upgraded successfully in venv.")
        except subprocess.CalledProcessError as e:
            # Non è critico se l'upgrade di pip fallisce, quindi solo un warning
            logger.warning(
                f"Failed to upgrade pip in venv '{self.venv_path}': {e.stderr}"
            )

    def _cleanup(self):
        """Removes the temporary virtual environment directory."""
        if self.venv_path and self.venv_path.exists():
            logger.info(
                f"Cleaning up temporary venv for '{self.project_name}' at: {self.venv_path}"
            )
            try:
                shutil.rmtree(self.venv_path)
                logger.info(f"Venv '{self.venv_path}' removed successfully.")
            except OSError as e:  # Può fallire su Windows se i file sono bloccati
                logger.error(
                    f"Error removing venv '{self.venv_path}': {e}. Manual cleanup might be needed."
                )
        self.venv_path = None
        self.python_executable = None
        self.pip_executable = None

    def __enter__(self):
        self._create_venv()
        if not self.python_executable or not self.pip_executable:
            raise RuntimeError(
                f"Venv for {self.project_name} was not properly initialized."
            )
        return self  # Rende l'istanza stessa disponibile nel blocco 'with'

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()
        # Non sopprimere le eccezioni, lasciale propagare
        return False
