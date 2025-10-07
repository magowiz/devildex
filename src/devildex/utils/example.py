import logging

from devildex.utils.venv_cm import IsolatedVenvManager

logger = logging.getLogger(__name__)

def main():
    with IsolatedVenvManager(project_name="mio_project") as venv_manager:
        logger.info("Using Python da: %s", venv_manager.python_executable)
        logger.info("Using pip da: %s", venv_manager.pip_executable)

    logger.info("Environment virtual per mio_project removed.")

if __name__ == "__main__":
    main()