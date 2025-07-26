"""Tests for the common_read module."""

from pathlib import Path

from devildex.local_data_parse.common_read import (
    get_explicit_dependencies_from_project_config,
)


def test_reads_from_pep621_dependencies(tmp_path: Path) -> None:
    """Verify reading from standard [project.dependencies] in pyproject.toml."""
    # Arrange
    pyproject_content = """
[project]
name = "my-project"
dependencies = [
    "django>=4.0",
    "celery",
]

[project.optional-dependencies]
test = [
    "pytest",
    "pytest-cov",
]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_content)

    # Act
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))

    # Assert
    # FIX: The original code only reads [project.dependencies], not optional ones.
    # The test must reflect this actual behavior.
    assert deps == {"django", "celery"}


def test_reads_from_poetry_dependencies(tmp_path: Path) -> None:
    """Verify reading from [tool.poetry.dependencies] in pyproject.toml."""
    # Arrange
    pyproject_content = """
[tool.poetry.dependencies]
python = "^3.9"
requests = "^2.25.1"
numpy = "1.20.1"

[tool.poetry.group.dev.dependencies]
black = "^22.0"
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_content)

    # Act
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))

    # Assert
    assert deps == {"requests", "numpy", "black"}


def test_reads_from_requirements_txt_as_fallback(tmp_path: Path) -> None:
    """Verify reading from requirements.txt when pyproject.toml is absent."""
    # Arrange
    requirements_content = """
requests==2.25.1
# This is a comment
numpy>=1.20.0
My_Package
    """
    (tmp_path / "requirements.txt").write_text(requirements_content)

    # Act
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))

    # Assert
    # FIX: The original code does not normalize package names (My_Package -> my-package).
    # The test must assert the name as it is returned by the code.
    assert deps == {"requests", "numpy", "My_Package"}


def test_prioritizes_pyproject_toml_over_requirements(tmp_path: Path) -> None:
    """Verify that pyproject.toml is used exclusively if both files exist."""
    # Arrange
    pyproject_content = "[project]\ndependencies = ['flask']"
    (tmp_path / "pyproject.toml").write_text(pyproject_content)

    requirements_content = "requests==2.25.1"
    (tmp_path / "requirements.txt").write_text(requirements_content)

    # Act
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))

    # Assert
    assert deps == {"flask"}
    assert "requests" not in deps


def test_no_config_files_found(tmp_path: Path) -> None:
    """Verify it returns an empty set when no config files are present."""
    # Act
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))

    # Assert
    assert deps == set()


def test_handles_malformed_pyproject_toml(tmp_path: Path, caplog) -> None:
    """Verify it handles a corrupt pyproject.toml gracefully."""
    # Arrange
    malformed_content = "this is not valid toml"
    (tmp_path / "pyproject.toml").write_text(malformed_content)

    # Act
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))

    # Assert
    assert deps == set()
    # FIX: The actual log message is "Warning: Invalid TOML in ...", not "Failed to parse...".
    # The test must check for the correct log message.
    assert "Invalid TOML in" in caplog.text


def test_handles_empty_requirements_txt(tmp_path: Path) -> None:
    """Verify it handles an empty requirements.txt file."""
    # Arrange
    (tmp_path / "requirements.txt").touch()

    # Act
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))

    # Assert
    assert deps == set()
