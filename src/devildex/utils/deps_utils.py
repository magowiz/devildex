"""deps utils module."""

import logging
from pathlib import Path

from pip_requirements_parser import RequirementsFile  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def _process_requirements_obj(
    requirements_file_obj: RequirementsFile,
    file_path_for_logging: Path,
    lines_to_explicitly_remove: set[str],
) -> list[str]:
    """Process to Requirements file to extract valid lines and log invalid ones."""
    valid_lines: list[str] = []
    for req in requirements_file_obj.requirements:
        if req.line:
            stripped_line = req.line.strip()
            if stripped_line in lines_to_explicitly_remove:
                logger.info(
                    "Explicit removal of the line '%s' from '%s'",
                    stripped_line,
                    file_path_for_logging,
                )
            else:
                valid_lines.append(req.line)
    if requirements_file_obj.invalid_lines:
        invalid_line_content_count = sum(
            1
            for inv_line in requirements_file_obj.invalid_lines
            if inv_line.line and inv_line.line.strip()
        )
        if invalid_line_content_count > 0:
            logger.warning(
                "Found %s RS ROWS NOT VALID (landfill from the parser) in ' %s'.",
                invalid_line_content_count,
                file_path_for_logging,
            )
    return valid_lines


def filter_requirements_lines(file_path_str: str) -> list[str] | None:
    """Read a file requirements.txt, filter non -valid lines.

        Using Pip-Requirements-Parser and returns a list of strings of
        Valid requirement.

    Args:
        file_path_str (str): Path to the Requirements.txt file from Read.

    Returns:
        List [str] | None: a list of strings, each representing a line
                          valid requirement. Returns none if the file does not
                          It can be read, the library is not available, or yes
                          Check an unexpected mistake. Return a list
                          empty if there are no valid requirements.

    """
    if RequirementsFile is None:
        logger.error(
            "The 'pip-requirements-parser' package is not installed."
            "Unable to filter the requirements file."
        )
        return None

    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error("requirements file '%s' not found.", file_path)
        return None

    lines_to_explicitly_remove = {"-e .", "-e."}

    try:
        logger.debug("Attempt to parse and filter: %s", file_path)
        requirements_file_obj = RequirementsFile.from_file(str(file_path))

        valid_lines = _process_requirements_obj(
            requirements_file_obj, file_path, lines_to_explicitly_remove
        )

        logger.debug(
            "Numero di rows valid extract da '%s': %s", file_path, len(valid_lines)
        )
    except (OSError, UnicodeDecodeError):
        logger.exception(
            "Decode or I/O error during parsing file '%s'",
            file_path,
        )
        return None
    else:
        return valid_lines
