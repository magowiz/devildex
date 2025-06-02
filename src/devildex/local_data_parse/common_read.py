"""common read module."""
import logging
import os
import sys

import toml
from packaging.requirements import InvalidRequirement, Requirement

logger = logging.getLogger(__name__)

def find_pyproject_toml(start_path: str = ".") -> str | None:
    """Cerca pyproject.toml nella directory start_path e nelle sue parent directories.

    Returns il absolute path o None se non trovato.
    """
    current_path = os.path.abspath(start_path)
    while True:
        pyproject_path = os.path.join(current_path, "pyproject.toml")
        if os.path.exists(pyproject_path):
            return pyproject_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            return None
        current_path = parent_path


def add_deps_from_section(section_data: dict, explicit_deps: set) -> None:
    """Add read dependencies from a specific section to explicit deps."""
    if isinstance(section_data, dict):
        for name in section_data:
            normalized_name = name.lower().replace("_", "-")
            if normalized_name != "python":
                explicit_deps.add(normalized_name)


def _read_and_parse_pyproject_toml(pyproject_path: str) -> dict | None:
    """Read and parses a pyproject.toml file.

    Args:
        pyproject_path: The path to the pyproject.toml file.

    Returns:
        A dictionary with the parsed TOML data, or None if an error occurs.

    """
    try:
        with open(pyproject_path, encoding="utf-8") as f:
            return toml.load(f)
    except FileNotFoundError:
        return None
    except toml.TomlDecodeError:
        logger.exception(
            f"Warning: Invalid TOML in {pyproject_path}. "
            "Cannot read explicit dependencies."
        )
        return None
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            f"Warning: Unexpected error reading {pyproject_path}: {e}"
        )
        return None


def get_explicit_poetry_dependencies(pyproject_path: str | None) -> set[str]:
    """Read pyproject.toml and returns a set con i nomi delle direct dependencies.

    (from sections tool.poetry.dependencies e tool.poetry.group.*.dependencies).
    Requires that 'toml' is importable.

    Args:
        pyproject_path (str | None): Il path al file pyproject.toml.

    Returns:
        set[str]: A set di strings containing explicit dependencies names.
                  Returns un empty set if file not exist, not readable,
                  not a valid Poetry project, or haven't got explicit dependencies.

    """
    explicit_deps: set[str] = set()
    if not pyproject_path:
        return explicit_deps

    pyproject_data = _read_and_parse_pyproject_toml(pyproject_path)
    if not pyproject_data:
        return explicit_deps

    tool_data = pyproject_data.get("tool", {})
    poetry_data = tool_data.get("poetry", {})

    main_deps_data = poetry_data.get("dependencies")
    if main_deps_data:
        add_deps_from_section(main_deps_data, explicit_deps)

    group_section_data = poetry_data.get("group", {})
    if isinstance(group_section_data, dict):
        for _group_name, group_content in group_section_data.items():
            if isinstance(group_content, dict):
                group_deps_data = group_content.get("dependencies")
                if group_deps_data:
                    add_deps_from_section(group_deps_data, explicit_deps)

    return explicit_deps


def _parse_requirement_line(line_content: str, filepath_for_log: str) -> str | None:
    """Parse a single line from a requirements file.

    Args:
        line_content: The content of the line to parse.
        filepath_for_log: The path of the requirements file, for logging purposes.

    Returns:
        The package name if successfully parsed, otherwise None.

    """
    stripped_line = line_content.strip()
    if (
        not stripped_line
        or stripped_line.startswith("#")
        or stripped_line.startswith("-")
        or stripped_line.startswith("--")
    ):
        return None

    try:
        req = Requirement(stripped_line)

    except InvalidRequirement:
        logger.exception(
            f"Warning: Invalid requirement line in {filepath_for_log}: "
            f"'{stripped_line}'"
        )
        return None
    else:
        return req.name


def get_explicit_package_names_from_requirements(
    requirements_filepath: str | None,
) -> set[str]:
    """Read a requirements.txt file and returns a set with explicit package names.

    Uses packaging.requirements for robust parsing.

    Args:
        requirements_filepath: The path to the requirements.txt file.

    Returns:
        A set of strings containing explicit package names.
        Returns an empty set if the file doesn't exist, cannot be read,
        or contains no valid requirements.
        May raise exceptions for critical unrecoverable errors not related to
        individual line parsing or basic file I/O.

    """
    explicit_package_names: set[str] = set()

    if not requirements_filepath:
        return explicit_package_names

    if not os.path.exists(requirements_filepath):
        logger.warning(
            f"Warning: Requirements file not found at {requirements_filepath}."
        )
        return explicit_package_names

    try:
        with open(requirements_filepath, encoding="utf-8") as f:
            for line in f:
                package_name = _parse_requirement_line(line, requirements_filepath)
                if package_name:
                    explicit_package_names.add(package_name)

    except (OSError, UnicodeDecodeError):
        logger.exception(
            f"Error reading or decoding requirements file {requirements_filepath}"
        )
        return set()
    return explicit_package_names


def find_requirements_txt(start_path: str = ".") -> str | None:
    """Cerca requirements.txt nella directory start_path e nelle sue parent directories.

    Returns il absolute path or None if not found.
    (Simile a find_pyproject_toml)
    """
    current_path = os.path.abspath(start_path)
    while True:
        reqs_path = os.path.join(current_path, "requirements.txt")
        if os.path.exists(reqs_path):
            return reqs_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            return None
        current_path = parent_path


def get_explicit_dependencies_from_project_config(start_path: str = ".") -> set[str]:
    """Cerca i file di configuration del project (pyproject.toml o requirements.txt).

    a starting from start_path e returns un set con i nomi delle explicit dependencies.
    Dà priority a pyproject.toml.

    Args:
        start_path (str): La directory da cui start the search (es. '.' per la CWD).

    Returns:
        set: Un set di strings con i nomi delle dependencies explicit.
             Returns an empty set if no valid configuration file is found
             o if there are read/parsing errors.
             Stampa warning/error su stderr.

    """
    pyproject_path = find_pyproject_toml(start_path)
    if pyproject_path:
        logger.info(f"Info: Found pyproject.toml at {pyproject_path}")
        return get_explicit_poetry_dependencies(pyproject_path)

    reqs_path = find_requirements_txt(start_path)
    if reqs_path:
        logger.info(f"Info: Found requirements.txt at {reqs_path}")
        return get_explicit_package_names_from_requirements(reqs_path)

    logger.warning(
        "Warning: No pyproject.toml or requirements.txt "
        f"found starting from {start_path}. "
        "Cannot determine explicit dependencies."
    )
    return set()


if __name__ == "__main__":
    logger.info("--- Testing project_config.py directly ---")

    explicit_names = get_explicit_dependencies_from_project_config("")

    if explicit_names:
        logger.info("\n--- Explicit Dependency Names Found ---")
        for ex_name in sorted(list(explicit_names)):
            logger.info(f"- {ex_name}")
        logger.info("--- End Explicit Dependency Names ---")
        sys.exit(0)
    else:
        logger.error(
            "\n--- No explicit dependency names found or config file missing ---"
        )
        sys.exit(1)
