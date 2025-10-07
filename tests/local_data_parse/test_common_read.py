"""Tests for the common_read module."""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from pytest_mock import MockerFixture

from devildex.local_data_parse.common_read import (
    _parse_pep621_dependencies,
    _parse_poetry_dependencies_sections,
    _parse_requirement_line,
    get_explicit_dependencies_from_project_config,
    get_explicit_package_names_from_requirements,
)


def test_reads_from_pep621_dependencies(tmp_path: Path) -> None:
    """Verify reading from standard [project.dependencies] in pyproject.toml."""
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
]"""
    (tmp_path / "pyproject.toml").write_text(pyproject_content)
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))
    assert deps == {"django", "celery"}


def test_reads_from_poetry_dependencies(tmp_path: Path) -> None:
    """Verify reading from [tool.poetry.dependencies] in pyproject.toml."""
    pyproject_content = """
[tool.poetry.dependencies]
python = "^3.9"
requests = "^2.25.1"
numpy = "1.20.1"

[tool.poetry.group.dev.dependencies]
black = "^22.0"
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_content)
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))
    assert deps == {"requests", "numpy", "black"}


def test_reads_from_requirements_txt_as_fallback(tmp_path: Path) -> None:
    """Verify reading from requirements.txt when pyproject.toml is absent."""
    requirements_content = """
requests==2.25.1
# This is a comment
numpy>=1.20.0
My_Package
    """
    (tmp_path / "requirements.txt").write_text(requirements_content)
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))
    assert deps == {"requests", "numpy", "My_Package"}


def test_prioritizes_pyproject_toml_over_requirements(tmp_path: Path) -> None:
    """Verify that pyproject.toml is used exclusively if both files exist."""
    pyproject_content = "[project]\ndependencies = ['flask']"
    (tmp_path / "pyproject.toml").write_text(pyproject_content)
    requirements_content = "requests==2.25.1"
    (tmp_path / "requirements.txt").write_text(requirements_content)
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))
    assert deps == {"flask"}
    assert "requests" not in deps


def test_no_config_files_found(tmp_path: Path) -> None:
    """Verify it returns an empty set when no config files are present."""
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))
    assert deps == set()


def test_handles_malformed_pyproject_toml(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Verify it handles a corrupt pyproject.toml gracefully."""
    malformed_content = "this is not valid toml"
    (tmp_path / "pyproject.toml").write_text(malformed_content)
    mock_logger = mocker.patch("devildex.local_data_parse.common_read.logger")
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))
    assert deps == set()
    mock_logger.exception.assert_called_once()


def test_handles_empty_requirements_txt(tmp_path: Path) -> None:
    """Verify it handles an empty requirements.txt file."""
    (tmp_path / "requirements.txt").touch()
    deps = get_explicit_dependencies_from_project_config(str(tmp_path))
    assert deps == set()


def test_parse_pep621_dependencies_non_list_deps() -> None:
    """Verify _parse_pep621_dependencies handles non-list dependencies."""
    explicit_deps = set()
    _parse_pep621_dependencies({"dependencies": "not a list"}, explicit_deps)
    assert explicit_deps == set()


def test_parse_pep621_dependencies_non_string_dep_item() -> None:
    """Verify _parse_pep621_dependencies handles non-string dependency items."""
    explicit_deps = set()
    _parse_pep621_dependencies({"dependencies": ["valid-dep", 123]}, explicit_deps)
    assert explicit_deps == {"valid-dep"}


@patch("devildex.local_data_parse.common_read.logger.warning")
def test_parse_requirement_line_invalid_requirement(
    mock_logger_warning: MagicMock,
) -> None:
    """Verify _parse_requirement_line handles InvalidRequirement."""
    result = _parse_requirement_line("invalid-package==", "fake_path.txt")
    assert result is None
    mock_logger_warning.assert_called_once()
    assert "Invalid requirement line" in mock_logger_warning.call_args[0][0]


def test_get_explicit_package_names_from_requirements_none_filepath() -> None:
    """Verify get_explicit_package_names_from_requirements handles None filepath."""
    result = get_explicit_package_names_from_requirements(None)
    assert result == set()


@patch("devildex.local_data_parse.common_read.logger.exception")
@patch("builtins.open", new_callable=mock_open)
@patch("os.path.exists", return_value=True)
def test_get_explicit_package_names_from_requirements_os_error(
    mock_exists: MagicMock, mock_open: MagicMock, mock_logger_exception: MagicMock
) -> None:
    """Verify get_explicit_package_names_from_requirements handles OSError."""
    mock_open.side_effect = OSError("Permission denied")
    result = get_explicit_package_names_from_requirements("/fake/reqs.txt")
    assert result == set()
    mock_logger_exception.assert_called_once()
    assert (
        "Error reading or decoding requirements file"
        in mock_logger_exception.call_args[0][0]
    )


@patch("devildex.local_data_parse.common_read.logger.exception")
@patch("builtins.open", new_callable=mock_open)
@patch("os.path.exists", return_value=True)
def test_get_explicit_package_names_from_requirements_unicode_error(
    mock_exists: MagicMock, mock_open: MagicMock, mock_logger_exception: MagicMock
) -> None:
    """Verify get_explicit_package_names_from_requirements handle UnicodeDecodeError."""
    mock_open.side_effect = UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid byte")
    result = get_explicit_package_names_from_requirements("/fake/reqs.txt")
    assert result == set()
    mock_logger_exception.assert_called_once()
    assert (
        "Error reading or decoding requirements file"
        in mock_logger_exception.call_args[0][0]
    )


def test_parse_poetry_dependencies_sections_non_dict_poetry_data() -> None:
    """Verify _parse_poetry_dependencies_sections handles non-dict poetry_data."""
    explicit_deps = set()
    _parse_poetry_dependencies_sections("not a dict", explicit_deps)
    assert explicit_deps == set()


def test_parse_poetry_dependencies_sections_empty_poetry_data() -> None:
    """Verify _parse_poetry_dependencies_sections handles empty poetry_data."""
    explicit_deps = set()
    _parse_poetry_dependencies_sections({}, explicit_deps)
    assert explicit_deps == set()
