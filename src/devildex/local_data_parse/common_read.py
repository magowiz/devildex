"""common read module."""

import logging
import os
import sys

import toml
from packaging.requirements import InvalidRequirement, Requirement

logger = logging.getLogger(__name__)

PYPROJECT_FILENAME = "pyproject.toml"


def find_pyproject_toml(start_path: str = ".") -> str | None:
    """Cerca pyproject.toml nella directory start_path e nelle sue parent directories.

    Returns il absolute path o None se non trovato.
    """
    current_path = os.path.abspath(start_path)
    while True:
        pyproject_path = os.path.join(current_path, PYPROJECT_FILENAME)
        if os.path.exists(pyproject_path):
            return pyproject_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            return None
        current_path = parent_path


def add_deps_from_poetry_section(section_data: dict, explicit_deps: set) -> None:
    """Add read dependencies from a specific Poetry dictionary section to explicit deps.

    Normalizes names (lowercase, hyphenated) and excludes 'python'.
    """
    if isinstance(section_data, dict):
        for name in section_data:
            normalized_name = name.lower().replace("_", "-")
            if normalized_name != "python":
                explicit_deps.add(normalized_name)


def _parse_pep621_dependencies(project_section: dict, explicit_deps: set[str]) -> None:
    """Parse [project.dependencies] from pyproject.toml data (PEP 621).

    Args:
        project_section: The dictionary representing the [project] section.
        explicit_deps: The set to add discovered dependency names to.

    """
    if not isinstance(project_section, dict):
        return

    project_deps_list = project_section.get("dependencies")
    if not isinstance(project_deps_list, list):
        return

    logger.info("Reading dependencies from [project.dependencies] (PEP 621)")
    for dep_string in project_deps_list:
        if isinstance(dep_string, str):
            package_name = _parse_requirement_line(
                dep_string, "pyproject.toml [project.dependencies]"
            )
            if package_name:
                explicit_deps.add(package_name)


def _read_and_parse_pyproject_toml(pyproject_path: str) -> dict | None:
    """Read and parses a pyproject.toml file.

    Args:
        pyproject_path: The path to the pyproject.toml file.

    Returns:
        A dictionary with the parsed TOML data, or None if an error occurs.

    """
    try:
        with open(pyproject_path, encoding="utf-8") as f_toml:
            return toml.load(f_toml)
    except FileNotFoundError:
        logger.warning(f"File pyproject.toml non trovato a: {pyproject_path}")
        return None
    except toml.TomlDecodeError:
        logger.exception(
            f"Warning: Invalid TOML in {pyproject_path}. "
            "Cannot read explicit dependencies."
        )
        return None
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(f"Warning: Unexpected error reading {pyproject_path}: {e}")
        return None


def _parse_requirement_line(line_content: str, filepath_for_log: str) -> str | None:
    """Parse a single line from a requirements file or a PEP 621 dependency string.

    Args:
        line_content: The content of the line to parse.
        filepath_for_log: The path/origin of the requirements, for logging purposes.

    Returns:
        The package name if successfully parsed, otherwise None.

    """
    stripped_line = line_content.strip()
    if (
        not stripped_line
        or stripped_line.startswith("#")
        or (
            filepath_for_log.endswith(".txt")
            and (stripped_line.startswith("-") or stripped_line.startswith("--"))
        )
    ):
        return None

    try:
        req = Requirement(stripped_line)
    except InvalidRequirement:
        logger.warning(
            f"Warning: Invalid requirement line in {filepath_for_log}: "
            f"'{stripped_line}'"
        )
        return None
    else:
        return req.name


def _get_explicit_dependencies_from_parsed_pyproject(
    pyproject_data: dict | None,
) -> set[str]:
    """Extract explicit dependencies from parsed pyproject.toml data.

    Prioritizes [project.dependencies] (PEP 621) and then checks
    [tool.poetry.dependencies] and [tool.poetry.group] sections for
    Poetry-specific definitions.

    Args:
        pyproject_data: Parsed content of pyproject.toml.

    Returns:
        A set of normalized explicit dependency names.

    """
    explicit_deps: set[str] = set()
    if not pyproject_data:
        logger.info("pyproject.toml data is empty, cannot extract dependencies.")
        return explicit_deps

    project_section = pyproject_data.get("project", {})
    _parse_pep621_dependencies(project_section, explicit_deps)

    tool_data = pyproject_data.get("tool", {})
    poetry_data = tool_data.get("poetry", {})
    _parse_poetry_dependencies_sections(poetry_data, explicit_deps)

    if not explicit_deps:
        logger.info(
            "No explicit dependencies were successfully extracted from "
            "[project.dependencies] or [tool.poetry] sections in pyproject.toml."
        )
    return explicit_deps


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
        with open(requirements_filepath, encoding="utf-8") as f_req:
            for line in f_req:
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


def _parse_poetry_dependencies_sections(
    poetry_data: dict, explicit_deps: set[str]
) -> None:
    """Parse [tool.poetry.dependencies] and [tool.poetry.group] sections.

    Args:
        poetry_data: The dictionary representing the [tool.poetry] section.
        explicit_deps: The set to add discovered dependency names to.

    """
    if not isinstance(poetry_data, dict) or not poetry_data:
        return

    logger.info(
        "Reading/adding dependencies from [tool.poetry.dependencies] and groups"
    )
    main_deps_data = poetry_data.get("dependencies")
    if main_deps_data:
        add_deps_from_poetry_section(main_deps_data, explicit_deps)

    group_section_data = poetry_data.get("group", {})
    if isinstance(group_section_data, dict):
        for _group_name, group_content in group_section_data.items():
            if isinstance(group_content, dict):
                group_deps_data = group_content.get("dependencies")
                if group_deps_data:
                    add_deps_from_poetry_section(group_deps_data, explicit_deps)


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

    """
    pyproject_path = find_pyproject_toml(start_path)
    if pyproject_path:
        logger.info(f"Info: Found pyproject.toml at {pyproject_path}")
        pyproject_data = _read_and_parse_pyproject_toml(pyproject_path)
        return _get_explicit_dependencies_from_parsed_pyproject(pyproject_data)

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


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(
        level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s"
    )
    logger.info("--- Testing common_read.py directly ---")

    dummy_project_path = "dummy_project_for_test"
    os.makedirs(dummy_project_path, exist_ok=True)
    dummy_pyproject_content_pep621 = """
[project]
name = "my-package"
version = "0.1.0"
description = "A sample package"
dependencies = [
    "requests>=2.0",
    "click",
    "Flask~=2.0"
]

[project.optional-dependencies]
test = ["pytest"]
"""
    dummy_pyproject_content_poetry = """
[tool.poetry]
name = "my-poetry-package"
version = "0.2.0"
description = ""
authors = ["Your Name <you@example.com>"]

[tool.poetry.dependencies]
python = "^3.8"
numpy = "^1.20"
pandas = { version = "^1.3", optional = true }

[tool.poetry.group.dev.dependencies]
pylint = "^2.10"
"""
    with open(
        os.path.join(dummy_project_path, PYPROJECT_FILENAME), "w", encoding="utf-8"
    ) as f:
        f.write(dummy_pyproject_content_pep621)

    logger.info(f"Testing with config in: {os.path.abspath(dummy_project_path)}")
    explicit_names = get_explicit_dependencies_from_project_config(dummy_project_path)

    if explicit_names:
        logger.info("\n--- Explicit Dependency Names Found ---")
        for ex_name in sorted(explicit_names):
            logger.info(f"- {ex_name}")
        logger.info("--- End Explicit Dependency Names ---")
    else:
        logger.error(
            "\n--- No explicit dependency names found or config file missing ---"
        )

    try:
        os.remove(os.path.join(dummy_project_path, PYPROJECT_FILENAME))
        os.rmdir(dummy_project_path)
        logger.info("Cleaned up dummy project.")
    except OSError:
        logger.exception("Error cleaning up dummy project")

    if explicit_names:
        sys.exit(0)
    else:
        sys.exit(1)
