"""venv context manager module."""

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

logger = logging.getLogger(__name__)


class IsolatedVenvManager:
    """A context manager to create and manage a Python virtual environment."""

    def __init__(self, project_name: str, base_temp_dir: Path | None = None) -> None:
        """Initialize the IsolatedVenvManager."""
        self.project_name = project_name
        self.base_temp_dir = base_temp_dir or Path(tempfile.gettempdir())
        self.venv_path: Path | None = None
        self.python_executable: str | None = None
        self.pip_executable: str | None = None

    def _create_venv(self) -> None:
        """Create the virtual environment."""
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
            subprocess.run(  # noqa: S603
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

    def _upgrade_pip(self) -> None:
        """Upgrades pip within the created virtual environment."""
        if not self.pip_executable:
            logger.warning("Pip executable not set, cannot upgrade pip.")
            return
        try:
            logger.info("Upgrading pip in venv: %s", self.venv_path)
            subprocess.run(  # noqa: S603
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

    def _cleanup(self) -> None:
        """Remove the temporary virtual environment directory."""
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

    def __enter__(self) -> "IsolatedVenvManager":
        """Set up the isolated virtual environment.

        This method is called when entering the 'with' statement. It creates
        the temporary virtual environment, sets up the paths to Python and pip
        executables within it, and upgrades pip.

        Returns:
            IsolatedVenvManager: The instance of the context manager itself,
                                 providing access to venv details like
                                 `python_executable` and `pip_executable`.

        Raises:
            RuntimeError: If the virtual environment cannot be properly
                          initialized (e.g., Python or pip executables
                          are not found after creation).

        """
        self._create_venv()
        if not self.python_executable or not self.pip_executable:
            raise RuntimeError(
                f"Venv for {self.project_name} was not properly initialized."
            )
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        """Clean up resources when exiting the context.

        This method is called automatically when the 'with' statement block is exited.
        It ensures that the temporary virtual environment is removed.

        Args:
            exc_type: The type of the exception that caused the context to be exited,
                      if an exception occurred. None otherwise.
            exc_val: The exception instance that caused the context to be exited,
                     if an exception occurred. None otherwise.
            exc_tb: A traceback object for the exception that caused the context
                    to be exited, if an exception occurred. None otherwise.

        Returns:
            False, indicating that any exception that occurred within the 'with'
            block should not be suppressed and should be re-raised.

        """
        _ = exc_type, exc_val, exc_tb
        self._cleanup()
        return False
