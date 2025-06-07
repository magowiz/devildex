"""module that parse a registered project data."""

import json
import logging
from pathlib import Path
from typing import Optional, TypedDict

from devildex.app_paths import AppPaths

logger = logging.getLogger(__name__)


REGISTRATION_FILE_NAME = "current_registered_project.json"
REGISTRY_SUBDIR = "registered_projects"


class RegisteredProjectData(TypedDict, total=False):
    """Class that implements RegisteredProjectData."""

    project_name: str
    project_path: str
    venv_path: str | None
    python_executable: str | None
    registration_timestamp_utc: str
    devildex_version_at_registration: str


def _parse_registration_content(file_path: Path) -> RegisteredProjectData | None:
    """Read, parses, and validates the content of a registration JSON file.

    Renamed with an underscore to indicate it's an internal helper function.
    """
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        required_keys = ["project_name", "project_path", "python_executable"]
        for key in required_keys:
            if key not in data or data[key] is None:
                logger.error(
                    f"Required key '{key}' missing or None in file: {file_path}"
                )
                return None

        for path_key in ["project_path", "venv_path", "python_executable"]:
            if path_key in data and data[path_key] is not None:
                try:
                    _ = Path(data[path_key]).resolve()
                    data[path_key] = str(Path(data[path_key]))
                except (TypeError, OSError, RuntimeError):
                    logger.warning(
                        f"Invalid path for '{path_key}' in "
                        f"{file_path}: {data[path_key]}"
                    )

    except FileNotFoundError:
        logger.info(f"Registration file not found during parsing: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.exception(f"Error decoding JSON from file: {file_path}")
        return None
    except OSError:
        logger.exception(f"Unexpected error while parsing file: {file_path}")
        return None
    else:
        return data


def save_active_registered_project(project_data: RegisteredProjectData) -> bool:
    """Save the provided project data as the actively registered project.

    Creates the necessary directory if it doesn't exist and writes the project
    data in JSON format to the registration file.

    Args:
        project_data: A dictionary containing the project details to save.
                      It should conform to the RegisteredProjectData structure.

    Returns:
        True if saving was successful, False otherwise.

    """
    try:
        app_paths = AppPaths()
        registry_base_dir = app_paths.user_data_dir / REGISTRY_SUBDIR

        registry_base_dir.mkdir(parents=True, exist_ok=True)

        registration_file_to_write = registry_base_dir / REGISTRATION_FILE_NAME
    except OSError:
        logger.exception(
            "Error determining or creating the path for the active project's "
            "registration file"
        )
        return False

    if not registration_file_to_write:
        logger.error(
            "Unable to determine the path for saving the active "
            "project registration file."
        )
        return False

    try:
        required_keys = ["project_name", "project_path", "python_executable"]
        for key in required_keys:
            if key not in project_data or project_data.get(key) is None:  # type: ignore
                logger.error(
                    f"Invalid project data for saving: required key '{key}'"
                    " missing or None."
                )
                return False

        with registration_file_to_write.open("w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=4)
        logger.info(
            f"Project '{project_data.get('project_name')}' "
            f"saved as active in: {registration_file_to_write}"
        )

    except OSError:
        logger.exception(
            f"I/O error while saving the active project to {registration_file_to_write}"
        )
    except TypeError:
        logger.exception(
            "Type error during JSON serialization for the active"
            f" project in {registration_file_to_write}"
        )
    except ValueError:
        logger.exception(
            "Unexpected error while saving the active project"
            f" to {registration_file_to_write}"
        )
    else:
        return True
    return False


def clear_active_registered_project() -> None:
    """Remove the file that stores the active project's state."""
    try:
        app_paths = AppPaths()
        registry_base_dir = app_paths.user_data_dir / REGISTRY_SUBDIR
        registration_file_to_clear = registry_base_dir / REGISTRATION_FILE_NAME
    except OSError:
        logger.exception(
            "Error determining the path of the registration file to be cleared."
        )
        return

    if not registration_file_to_clear:
        logger.error(
            "Unable to determine the path of the registration file to be cleared."
        )
        return

    try:
        if registration_file_to_clear.exists() and registration_file_to_clear.is_file():
            registration_file_to_clear.unlink()
            logger.info(f"Active project file removed: {registration_file_to_clear}")
        else:
            logger.info(
                f"No active project file to remove "
                f"(did not exist or was not a file): {registration_file_to_clear}"
            )
    except OSError:
        logger.exception(
            "Error while removing the active project "
            f"file: {registration_file_to_clear}"
        )


def load_active_registered_project() -> Optional[RegisteredProjectData]:
    """Load and parses the actively registered project.

    Determines the file path, reads it, and validates its content.
    Returns the project data or None if not registered or in case of an error.
    """
    registration_file_to_check: Optional[Path] = None
    try:
        app_paths = AppPaths()
        registry_base_dir = app_paths.user_data_dir / REGISTRY_SUBDIR
        if not registry_base_dir.exists():
            logger.debug(
                "The base directory for registration "
                f"({registry_base_dir}) does not exist."
            )
        else:
            registration_file_to_check = registry_base_dir / REGISTRATION_FILE_NAME
    except OSError:
        logger.exception("Error determining the path of the registration file.")

    if not registration_file_to_check:
        logger.info("Registration file path not determinable.")
        return None

    if not registration_file_to_check.is_file():
        logger.info(
            f"No actively registered project found "
            f"(missing file: {registration_file_to_check})."
        )
        return None

    logger.debug(f"Found registered project file: {registration_file_to_check}")
    project_data = _parse_registration_content(registration_file_to_check)

    if project_data:
        logger.info(
            f"Project '{project_data.get('project_name')}' loaded successfully."
        )
    return project_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    active_project = load_active_registered_project()
    if active_project:
        logger.info("Actively registered project loaded:")
        logger.info(f"  - Name: {active_project.get('project_name')}")
        logger.info(f"  - Venv Path: {active_project.get('venv_path')}")
        logger.info(f"  - Python Executable: {active_project.get('python_executable')}")
    else:
        logger.info("No actively registered project found or error during loading.")
