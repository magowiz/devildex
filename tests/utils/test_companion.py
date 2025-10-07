"""Tests for the companion script used for project registration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from devildex.app_paths import (
    ACTIVE_PROJECT_REGISTRATION_FILENAME,
    ACTIVE_PROJECT_REGISTRY_SUBDIR,
)
from devildex.utils import companion


@pytest.fixture
def mock_app_paths(tmp_path: Path, mocker: MockerFixture) -> Path:
    """Mock AppPaths to use a temporary directory for user data."""
    user_data_dir = tmp_path / "devildex_user_data"
    mocker.patch(
        "devildex.utils.companion.AppPaths.user_data_dir",
        new_callable=mocker.PropertyMock(return_value=user_data_dir),
    )
    return user_data_dir


def test_register_project_success(
    tmp_path: Path,
    mock_app_paths: Path,
    mocker: MockerFixture,
) -> None:
    """Verify a successful project registration creates the correct JSON file."""
    project_dir = tmp_path / "my-cool-project"
    project_dir.mkdir()
    venv_dir = tmp_path / "my-cool-venv"
    python_exe = (
        venv_dir / ("Scripts" if companion.os.name == "nt" else "bin") / "python"
    )
    python_exe.parent.mkdir(parents=True)
    python_exe.touch()
    mocker.patch.dict("os.environ", {"VIRTUAL_ENV": str(venv_dir)})
    mocker.patch("os.getcwd", return_value=str(project_dir))
    mock_logger = mocker.patch("devildex.utils.companion.logger")
    companion.register_project(project_path_str=None)
    registration_file = (
        mock_app_paths
        / ACTIVE_PROJECT_REGISTRY_SUBDIR
        / ACTIVE_PROJECT_REGISTRATION_FILENAME
    )
    assert registration_file.exists()

    with open(registration_file, encoding="utf-8") as f:
        data = json.load(f)

    assert data["project_name"] == "my-cool-project"
    assert data["project_path"] == str(project_dir.resolve())
    assert data["venv_path"] == str(venv_dir.resolve())
    assert data["python_executable"] == str(python_exe.resolve())
    assert "registration_timestamp_utc" in data
    assert "devildex_version_at_registration" in data

    mock_logger.info.assert_any_call("Project 'my-cool-project' registered successfully!")
    mock_logger.info.assert_any_call(f"Registration File: {registration_file}")


def test_register_project_no_venv(mocker: MockerFixture) -> None:
    """Verify registration fails gracefully when VIRTUAL_ENV is not set."""
    mock_logger = mocker.patch("devildex.utils.companion.logger")
    with patch.dict("os.environ", {}, clear=True):
        companion.register_project("/fake/project")
    mock_logger.error.assert_called_once_with(
        "Operation cancelled: no active user virtual environment (VIRTUAL_ENV) detected. Ensure you have activated the virtual environment of the project you wish to register."
    )


def test_register_project_no_python_executable(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Verify registration fails if the python executable is not found in the venv."""
    venv_dir = tmp_path / "bad-venv"
    venv_dir.mkdir()
    mocker.patch.dict("os.environ", {"VIRTUAL_ENV": str(venv_dir)})
    mock_logger = mocker.patch("devildex.utils.companion.logger")
    companion.register_project("/fake/project")
    mock_logger.error.assert_called_once_with(
        f"Operation cancelled: VIRTUAL_ENV '{venv_dir}' detected, but unable to determine the correct Python executable within it. Check the structure of your virtual environment."
    )


def test_register_project_invalid_project_path(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Verify registration fails if the provided project path is not a directory."""
    venv_dir = tmp_path / "my-cool-venv"
    python_exe = venv_dir / "bin" / "python"
    python_exe.parent.mkdir(parents=True)
    python_exe.touch()
    mocker.patch.dict("os.environ", {"VIRTUAL_ENV": str(venv_dir)})
    invalid_project_path = tmp_path / "not_a_directory"
    invalid_project_path.touch()
    mock_logger = mocker.patch("devildex.utils.companion.logger")
    companion.register_project(str(invalid_project_path))
    mock_logger.error.assert_called_once_with(
        f"The specified project path is not a valid directory: "
        f"{invalid_project_path.resolve()}"
    )


@patch("devildex.utils.companion.register_project")
def test_main_with_path_argument(
    mock_register_project: MagicMock, mocker: MockerFixture
) -> None:
    """Verify main() calls register_project with the provided path."""
    fake_path = "/my/awesome/project"
    mocker.patch("sys.argv", ["devildex-register-project", "--project-path", fake_path])
    companion.main()
    mock_register_project.assert_called_once_with(fake_path)


@patch("devildex.utils.companion.register_project")
def test_main_with_no_arguments(
    mock_register_project: MagicMock, mocker: MockerFixture
) -> None:
    """Verify main() calls register_project with None when no path is given."""
    mocker.patch("sys.argv", ["devildex-register-project"])
    companion.main()
    mock_register_project.assert_called_once_with(None)
