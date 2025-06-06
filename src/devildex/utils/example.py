"""example context manager venv."""
import logging

from devildex.utils.venv_cm import IsolatedVenvManager

PROJECT_NAME = "mio_project"
logger = logging.getLogger(__name__)
with IsolatedVenvManager(project_name=PROJECT_NAME) as venv_manager:
    logger.info(f"Using Python da: {venv_manager.python_executable}")
    logger.info(f"Using pip da: {venv_manager.pip_executable}")

logger.info(f"Environment virtual per {PROJECT_NAME} removed.")
