"""common read module."""

import os
import sys

import toml
from packaging.requirements import InvalidRequirement, Requirement


def find_pyproject_toml(start_path="."):
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


def add_deps_from_section(section_data, explicit_deps):
    """Add read dependencies from a specific section to explicit deps."""
    if isinstance(section_data, dict):
        for name in section_data.keys():
            normalized_name = name.lower().replace("_", "-")
            if normalized_name != "python":
                explicit_deps.add(normalized_name)


def _read_and_parse_pyproject_toml(pyproject_path: str) -> dict | None:
    """Reads and parses a pyproject.toml file.

    Args:
        pyproject_path: The path to the pyproject.toml file.

    Returns:
        A dictionary with the parsed TOML data, or None if an error occurs.
    """
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            return toml.load(f)
    except FileNotFoundError:
        # Consider using logging if this module gets a logger instance
        # print(f"Info: pyproject.toml not found at {pyproject_path}", file=sys.stderr)
        return None
    except toml.TomlDecodeError:
        print(
            f"Warning: Invalid TOML in {pyproject_path}. "
            "Cannot read explicit dependencies.",
            file=sys.stderr,
        )
        return None
    except Exception as e:  # pylint: disable=broad-except
        print(
            f"Warning: Unexpected error reading {pyproject_path}: {e}", file=sys.stderr
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


def get_explicit_package_names_from_requirements(requirements_filepath):
    """Read a requirements.txt file and return a set with explicit packages names.

    Use packaging.requirements for a robust parsing.
    Requires che 'packaging' sia importable.

    Args:
        requirements_filepath (str): Il path al file requirements.txt.

    Returns:
        set: A set of strings containing explicit packages names.
             Returns un empty set if file exist or there are
                 read/parsing errors.
    """
    explicit_package_names = set()

    if not requirements_filepath:
        return explicit_package_names

    if not os.path.exists(requirements_filepath):
        print(
            f"Warning: File requirements.txt not found at {requirements_filepath}.",
            file=sys.stderr,
        )
        return explicit_package_names

    try:
        with open(requirements_filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if (
                    not line
                    or line.startswith("#")
                    or line.startswith("-")
                    or line.startswith("--")
                ):
                    continue

                try:
                    req = Requirement(line)
                    explicit_package_names.add(req.name)
                except InvalidRequirement as e:
                    print(
                        "Warning: Invalid requirement line in "
                        f"{requirements_filepath}: '{line}' - {e}",
                        file=sys.stderr,
                    )

    except (IOError, UnicodeDecodeError) as e:

        # Catch specific file operation or decoding errors

        print(
            f"Error reading or decoding {requirements_filepath}: {e}", file=sys.stderr
        )

        return set()  # Maintain behavior of returning empty set for these issues

    except (KeyboardInterrupt, SystemExit):

        # Ensure these are not caught by a general Exception if one were added later

        raise

    return explicit_package_names


def find_requirements_txt(start_path="."):
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


def get_explicit_dependencies_from_project_config(start_path="."):
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
        print(f"Info: Found pyproject.toml at {pyproject_path}", file=sys.stderr)
        return get_explicit_poetry_dependencies(pyproject_path)

    reqs_path = find_requirements_txt(start_path)
    if reqs_path:
        print(f"Info: Found requirements.txt at {reqs_path}", file=sys.stderr)
        return get_explicit_package_names_from_requirements(reqs_path)

    print(
        "Warning: No pyproject.toml or requirements.txt "
        f"found starting from {start_path}. "
        "Cannot determine explicit dependencies.",
        file=sys.stderr,
    )
    return set()


if __name__ == "__main__":
    print("--- Testing project_config.py directly ---", file=sys.stderr)

    explicit_names = get_explicit_dependencies_from_project_config("")

    if explicit_names:
        print("\n--- Explicit Dependency Names Found ---", file=sys.stderr)
        for ex_name in sorted(list(explicit_names)):
            print(f"- {ex_name}", file=sys.stderr)
        print("--- End Explicit Dependency Names ---", file=sys.stderr)
        sys.exit(0)
    else:
        print(
            "\n--- No explicit dependency names found or config file missing ---",
            file=sys.stderr,
        )
        sys.exit(1)
