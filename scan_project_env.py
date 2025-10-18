"""scan project env module."""

import logging
import os
import sys
from pathlib import Path

import toml

logger = logging.getLogger(__name__)


def find_pyproject_toml(start_path: str = ".") -> Path | None:
    """Cerca pyproject.toml nella current directory or nelle parent directory.

    Returns:
        absolute path or None se non trovato.

    """
    current_path = os.path.abspath(start_path)
    while True:
        pyproject_path = os.path.join(current_path, "pyproject.toml")
        if os.path.exists(pyproject_path):
            return Path(pyproject_path)
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            return None
        current_path = parent_path


def _read_project_data_toml(pyproject_path: Path | str) -> set | dict:
    try:
        with open(pyproject_path, encoding="utf-8") as f:
            pyproject_data = toml.load(f)
    except FileNotFoundError:
        logger.exception(
            f"Error: File pyproject.toml non trovato a {pyproject_path}.",
        )
        return set()
    except toml.TomlDecodeError:
        logger.exception(
            f"Error: Unable to decode TOML file: {pyproject_path}.",
        )
        return set()
    return pyproject_data


def _add_deps_from_section(section_data: dict, deps_set: set) -> None:
    if isinstance(section_data, dict):
        for name in section_data:
            normalized_name = name.lower().replace("_", "-")
            if normalized_name != "python":
                deps_set.add(normalized_name)


def get_explicit_poetry_dependencies(pyproject_path: Path) -> set:
    """Read pyproject.toml e returns un set con i nomi delle direct dependencies.

    (from tool.poetry.dependencies and tool.poetry.group.*.dependencies sections).
    """
    pyproject_data = _read_project_data_toml(pyproject_path)
    explicit_deps: set[str] = set()
    if (
        "tool" in pyproject_data
        and "poetry" in pyproject_data["tool"]
        and "dependencies" in pyproject_data["tool"]["poetry"]
    ):
        _add_deps_from_section(
            pyproject_data["tool"]["poetry"]["dependencies"], explicit_deps
        )

    if (
        "tool" in pyproject_data
        and "poetry" in pyproject_data["tool"]
        and "group" in pyproject_data["tool"]["poetry"]
    ):
        for _, group_data in pyproject_data["tool"]["poetry"]["group"].items():
            if isinstance(group_data, dict) and "dependencies" in group_data:
                _add_deps_from_section(group_data["dependencies"], explicit_deps)

    return explicit_deps


if __name__ == "__main__":
    pyproject_path1 = find_pyproject_toml(".")

    if not pyproject_path1:
        logger.error(
            "Error: pyproject.toml non trovato. "
            "Unable to determine explicit dependencies.",
        )
        sys.exit(1)

    explicit_package_names = get_explicit_poetry_dependencies(pyproject_path1)

    if not explicit_package_names:
        logger.warning(
            "Warning: No explicit dependencies found in "
            "pyproject.toml (other than python).",
        )

    sys.exit(0)
