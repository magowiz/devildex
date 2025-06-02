"""example context manager venv."""
import logging

from devildex.utils.venv_cm import IsolatedVenvManager

PROJECT_NAME = "mio_progetto"
logger = logging.getLogger(__name__)
with IsolatedVenvManager(project_name=PROJECT_NAME) as venv_manager:
    logger.info(f"Usando Python da: {venv_manager.python_executable}")
    logger.info(f"Usando pip da: {venv_manager.pip_executable}")

logger.info(f"Ambiente virtuale per {PROJECT_NAME} rimosso.")
