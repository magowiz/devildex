"""venv context manager module."""

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class IsolatedVenvManager:
    """A context manager to create and manage a temp isolated Python virtual environment."""

    def __init__(self, project_name: str, base_temp_dir: Path | None = None):
        """Initializes the IsolatedVenvManager."""
        self.project_name = project_name
        self.base_temp_dir = base_temp_dir or Path(tempfile.gettempdir())
        self.venv_path: Path | None = None
        self.python_executable: str | None = None
        self.pip_executable: str | None = None

    def _create_venv(self):
        """Creates the virtual environment."""
        self.venv_path = Path(
            tempfile.mkdtemp(
                prefix=f"devildex_venv_{self.project_name}_", dir=self.base_temp_dir
            )
        )
        logger.info(
            "Creating temporary venv for '%s' at: %s", self.project_name, self.venv_path
        )
        print(f"DEBUG VENV_CM: Attempting to create venv at: {self.venv_path}")

        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(self.venv_path)],
                check=True,
                capture_output=True,
                text=True,
            )

            bin_dir = self.venv_path / ("Scripts" if sys.platform == "win32" else "bin")
            self.python_executable = str(
                bin_dir / ("python.exe" if sys.platform == "win32" else "python")
            )
            self.pip_executable = str(
                bin_dir / ("pip.exe" if sys.platform == "win32" else "pip")
            )
            print(
                f"DEBUG VENV_CM: VENV CREATED. Python executable: "
                f"{self.python_executable}"
            )
            print(f"DEBUG VENV_CM: VENV CREATED. Pip executable: {self.pip_executable}")
            print(
                "DEBUG VENV_CM: VENV CREATED. Does python exist? %s",
                Path(self.python_executable).exists(),
            )
            print(
                "DEBUG VENV_CM: VENV CREATED. Does pip exist? "
                f"{Path(self.pip_executable).exists()}"
            )

            logger.info("Venv for '%s' created successfully.", self.project_name)
            logger.info("  Python executable: %s", self.python_executable)
            logger.info("  Pip executable: %s", self.pip_executable)

            self._upgrade_pip()

        except subprocess.CalledProcessError as e:
            logger.error(
                "Failed to create venv for '%s': %s", self.project_name, e.stderr
            )
            self._cleanup()
            raise
        except Exception as e:
            logger.error(
                "An unexpected error occurred during venv creation for '%s': %s",
                self.project_name,
                e,
            )
            self._cleanup()
            raise

    def _upgrade_pip(self):
        """Upgrades pip within the created virtual environment."""
        if not self.pip_executable:
            logger.warning("Pip executable not set, cannot upgrade pip.")
            return
        try:
            logger.info("Upgrading pip in venv: %s", self.venv_path)
            subprocess.run(
                [self.python_executable, "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
                cwd=self.venv_path,
            )
            logger.info("Pip upgraded successfully in venv.")
        except subprocess.CalledProcessError as e:
            logger.warning(
                "Failed to upgrade pip in venv '%s': %s", self.venv_path, e.stderr
            )

    def _cleanup(self):
        """Removes the temporary virtual environment directory."""
        if self.venv_path and self.venv_path.exists():
            logger.info(
                "Cleaning up temporary venv for '%s' at: %s",
                self.project_name,
                self.venv_path,
            )
            try:
                shutil.rmtree(self.venv_path)
                logger.info("Venv '%s' removed successfully.", self.venv_path)
            except OSError as e:
                logger.error(
                    "Error removing venv '%s': %s. Manual cleanup might be needed.",
                    self.venv_path,
                    e,
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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()
        return False
