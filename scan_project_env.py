"""scan project env module."""

import os
import sys
from pathlib import Path

import toml


def find_pyproject_toml(start_path: str = ".") -> Path | None:
    """Cerca pyproject.toml nella current directory or nelle parent directory.

    Returns:
        absolute path or None se non trovato.

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


def _read_project_data_toml(pyproject_path: Path | str) -> set | dict:
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            pyproject_data = toml.load(f)
    except FileNotFoundError:
        print(
            f"Error: File pyproject.toml non trovato a {pyproject_path}.",
            file=sys.stderr,
        )
        return set()
    except toml.TomlDecodeError:
        print(
            f"Error: Unable to decode TOML file: {pyproject_path}.",
            file=sys.stderr,
        )
        return set()
    return pyproject_data


def get_explicit_poetry_dependencies(pyproject_path: Path) -> set:
    """Read pyproject.toml e returns un set con i nomi delle direct dependencies.

    (from tool.poetry.dependencies and tool.poetry.group.*.dependencies sections).
    """
    pyproject_data = _read_project_data_toml(pyproject_path)
    explicit_deps = set()

    def add_deps_from_section(section_data: dict) -> None:
        if isinstance(section_data, dict):
            for name in section_data.keys():
                normalized_name = name.lower().replace("_", "-")
                if normalized_name != "python":
                    explicit_deps.add(normalized_name)

    if (
        "tool" in pyproject_data
        and "poetry" in pyproject_data["tool"]
        and "dependencies" in pyproject_data["tool"]["poetry"]
    ):
        add_deps_from_section(pyproject_data["tool"]["poetry"]["dependencies"])

    if (
        "tool" in pyproject_data
        and "poetry" in pyproject_data["tool"]
        and "group" in pyproject_data["tool"]["poetry"]
    ):
        for group_name, group_data in pyproject_data["tool"]["poetry"]["group"].items():
            if isinstance(group_data, dict) and "dependencies" in group_data:
                add_deps_from_section(group_data["dependencies"])

    return explicit_deps


if __name__ == "__main__":
    pyproject_path1 = find_pyproject_toml(".")

    if not pyproject_path1:
        print(
            "Error: pyproject.toml non trovato. "
            "Unable to determine explicit dependencies.",
            file=sys.stderr,
        )
        sys.exit(1)

    explicit_package_names = get_explicit_poetry_dependencies(pyproject_path1)

    if not explicit_package_names:
        print(
            "Warning: No explicit dependencies found in "
            "pyproject.toml (other than python).",
            file=sys.stderr,
        )

    sys.exit(0)
