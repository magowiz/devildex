"""companion to get basic data from project."""
import argparse
import datetime
import json
import logging
import os
import sys
from pathlib import Path

from devildex.app_paths import AppPaths
from devildex.info import APPLICATION_NAME
from devildex.info import VERSION as DEVILDEX_VERSION

logging.basicConfig(
    level=logging.INFO,
    format=f"[%(asctime)s - {APPLICATION_NAME.upper()}_REGISTRAR - "
           "%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)



REGISTRY_SUBDIR = "registered_projects"
FIXED_REGISTRATION_FILE_NAME = "current_registered_project.json"




def get_active_user_venv_info() -> tuple[Path | None, str | None]:
    """Determine the venv path and Python executable using the VIRTUAL_ENV environment variable.

    Returns:
        tuple[Path | None, str | None]: (active_user_venv_path,
            user_python_executable_path)
            or (None, None) if VIRTUAL_ENV is not set.

    """
    virtual_env_path_str = os.environ.get("VIRTUAL_ENV")

    if not virtual_env_path_str:
        logger.info(
            "VIRTUAL_ENV not set. Unable to identify an active user "
            "virtual environment."
        )
        return None, None

    venv_path = Path(virtual_env_path_str).resolve()
    logger.debug(f"Active user venv identified via VIRTUAL_ENV: {venv_path}")

    python_exe_name = "python.exe" if os.name == "nt" else "python"
    scripts_dir_name = "Scripts" if os.name == "nt" else "bin"
    python_exe_path = venv_path / scripts_dir_name / python_exe_name

    if python_exe_path.exists() and python_exe_path.is_file():
        logger.debug(f"Python executable for user VIRTUAL_ENV: {python_exe_path}")
        return venv_path, str(python_exe_path)

    logger.warning(
        f"VIRTUAL_ENV is '{venv_path}', but the expected Python executable "
        f"was not found at '{python_exe_path}'. "
        "The venv registration might not be complete."
    )
    return venv_path, None


def register_project(project_path_str: str | None) -> None:
    """Collect information about the project and the active user venv and saves it."""
    active_venv_path, active_python_executable = get_active_user_venv_info()

    if not active_venv_path:
        logger.error(
            "Operation cancelled: no active user virtual environment "
            "(VIRTUAL_ENV) detected. "
            "Ensure you have activated the virtual environment of the "
            "project you wish to register."
        )
        return

    if not active_python_executable:
        logger.error(
            f"Operation cancelled: VIRTUAL_ENV '{active_venv_path}'"
            " detected, but unable to determine the correct Python executable within it. "
            "Check the structure of your virtual environment."
        )
        return

    if project_path_str:
        project_path = Path(project_path_str).resolve()
        if not project_path.is_dir():
            logger.error(
                f"The specified project path is not a valid directory: {project_path}"
            )
            return
    else:
        project_path = Path(os.getcwd()).resolve()
        logger.info(f"Using current directory as project path: {project_path}")

    project_name = project_path.name

    app_paths_manager = AppPaths()
    registry_dir = app_paths_manager.user_data_dir / REGISTRY_SUBDIR
    registry_dir.mkdir(parents=True, exist_ok=True)

    registration_file = registry_dir / FIXED_REGISTRATION_FILE_NAME


    project_data = {
        "project_name": project_name,
        "project_path": str(project_path),
        "venv_path": str(active_venv_path),
        "python_executable": active_python_executable,
        "registration_timestamp_utc": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "devildex_version_at_registration": DEVILDEX_VERSION,
    }

    try:
        with open(registration_file, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=4)
        logger.info(f"Project '{project_name}' registered successfully!")
        logger.info(f"User Venv Path: {active_venv_path}")
        logger.info(f"User Python Executable: {active_python_executable}")
        logger.info(f"Project Path: {project_path}")
        logger.info(f"Registration File: {registration_file}")
    except OSError:
        logger.exception(f"Error writing the registration file {registration_file}")
    except (TypeError, ValueError):
        logger.exception(f"Unexpected error while registering project {project_name}.")


def main() -> None:
    """Implement Main method."""
    parser = argparse.ArgumentParser(
        description=(
            "Registers the current project and its virtual environment with DevilDex. "
            "This script should be run from within the ACTIVATED venv "
            "of the project you wish to register."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--project-path",
        type=str,
        default=None,
        help=(
            "Optional path to the project's root directory.\n"
            "If not provided, the current working directory is used."
        ),
    )
    args = parser.parse_args()

    logger.info("Starting project registration for DevilDex...")
    register_project(args.project_path)


if __name__ == "__main__":
    main()
