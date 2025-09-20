"""Tests for the registered_project_parser module."""

import json
import logging
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.local_data_parse import registered_project_parser
from devildex.local_data_parse.registered_project_parser import RegisteredProjectData

TEST_PROJECT_DATA: RegisteredProjectData = {
    "project_name": "MyTestProject",
    "project_path": "/fake/path/to/project",
    "python_executable": "/fake/venv/bin/python",
}


@pytest.fixture
def mock_app_paths(tmp_path: Path, mocker: MockerFixture) -> Path:
    """Mock AppPaths to use a temporary user_data_dir."""
    mock_user_data_dir = tmp_path / "user_data"
    mock_user_data_dir.mkdir()
    expected_file_path = (
        mock_user_data_dir
        / registered_project_parser.REGISTRY_SUBDIR
        / registered_project_parser.REGISTRATION_FILE_NAME
    )
    expected_file_path.parent.mkdir(parents=True, exist_ok=True)

    mock_app_paths_class = mocker.patch(
        "devildex.local_data_parse.registered_project_parser.AppPaths"
    )
    mock_app_paths_instance = mock_app_paths_class.return_value
    mock_app_paths_instance.user_data_dir = mock_user_data_dir
    return expected_file_path


def test_save_and_load_active_project(mock_app_paths: Path) -> None:
    """Verify that project data can be saved to a JSON file and loaded back."""
    registered_project_parser.save_active_registered_project(TEST_PROJECT_DATA)
    assert mock_app_paths.is_file()
    with open(mock_app_paths) as f:
        content_on_disk = json.load(f)
    assert content_on_disk == TEST_PROJECT_DATA
    loaded_data = registered_project_parser.load_active_registered_project()
    assert loaded_data is not None
    assert loaded_data["project_name"] == "MyTestProject"
    assert loaded_data == TEST_PROJECT_DATA


def test_load_active_project_file_not_found(mock_app_paths: Path) -> None:
    """Verify that loading returns None when the active project file does not exist."""
    assert not mock_app_paths.exists()
    loaded_data = registered_project_parser.load_active_registered_project()
    assert loaded_data is None


def test_load_active_project_invalid_json(mock_app_paths: Path, caplog) -> None:
    """Verify that loading returns None and logs an error for a corrupt JSON file."""
    mock_app_paths.write_text("this is not valid json {")
    assert mock_app_paths.is_file()
    loaded_data = registered_project_parser.load_active_registered_project()
    assert loaded_data is None
    assert "Error decoding JSON from file" in caplog.text
    assert str(mock_app_paths) in caplog.text


def test_load_active_project_missing_required_keys(
    mock_app_paths: Path, caplog
) -> None:
    """Verify loading fails if the JSON is valid but missing required keys."""
    corrupt_data = {"project_name": "Incomplete", "project_path": "/path"}
    mock_app_paths.write_text(json.dumps(corrupt_data))
    loaded_data = registered_project_parser.load_active_registered_project()
    assert loaded_data is None
    assert "Required key 'python_executable' missing or None" in caplog.text


def test_clear_active_registered_project(mock_app_paths: Path) -> None:
    """Verify that clearing the active project deletes the corresponding file."""
    mock_app_paths.write_text(json.dumps(TEST_PROJECT_DATA))
    assert mock_app_paths.is_file()
    registered_project_parser.clear_active_registered_project()
    assert not mock_app_paths.exists()


def test_clear_active_registered_project_file_not_exist(mock_app_paths: Path) -> None:
    """Verify that clearing does not raise an error if the file is already gone."""
    assert not mock_app_paths.exists()
    try:
        registered_project_parser.clear_active_registered_project()
    except Exception as e:
        pytest.fail(
            f"clear_active_registered_project raised an exception unexpectedly: {e}"
        )


def test_save_active_project_missing_required_keys(caplog) -> None:
    """Verify that saving fails if the input data is missing required keys."""
    invalid_data: RegisteredProjectData = {  # type: ignore
        "project_name": "Invalid",
        "python_executable": "/bin/python",
    }
    result = registered_project_parser.save_active_registered_project(invalid_data)
    assert result is False
    assert "required key 'project_path' missing or None" in caplog.text


def test_load_active_project_invalid_path_in_json(mock_app_paths: Path, caplog) -> None:
    """Verify that loading handles an invalid path in the JSON file."""
    invalid_path_data = {
        "project_name": "InvalidPathProject",
        "project_path": "/fake/path/to/project",
        "python_executable": "/fake/venv/bin/python\0",
    }
    mock_app_paths.write_text(json.dumps(invalid_path_data))
    loaded_data = registered_project_parser.load_active_registered_project()
    assert loaded_data is not None
    assert "Invalid path for 'python_executable'" in caplog.text


def test_load_active_project_os_error_on_open(
    mock_app_paths: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that loading handles an OSError when opening the file."""
    mock_app_paths.write_text(json.dumps(TEST_PROJECT_DATA))
    mocker.patch.object(Path, "open", side_effect=OSError("Test OSError"))
    loaded_data = registered_project_parser.load_active_registered_project()
    assert loaded_data is None
    assert "Unexpected error while parsing file" in caplog.text


def test_save_active_project_mkdir_os_error(mocker: MockerFixture, caplog) -> None:
    """Verify that saving handles an OSError during directory creation."""
    mocker.patch.object(Path, "mkdir", side_effect=OSError("Test mkdir OSError"))
    result = registered_project_parser.save_active_registered_project(TEST_PROJECT_DATA)
    assert result is False
    assert "Error determining or creating the path" in caplog.text


def test_save_active_project_open_os_error(
    mock_app_paths: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that saving handles an OSError when opening the file for writing."""
    mocker.patch.object(Path, "open", side_effect=OSError("Test open OSError"))
    result = registered_project_parser.save_active_registered_project(TEST_PROJECT_DATA)
    assert result is False
    assert "I/O error while saving the active project" in caplog.text


def test_save_active_project_json_type_error(
    mock_app_paths: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that saving handles a TypeError during JSON serialization."""
    mocker.patch("json.dump", side_effect=TypeError("Test TypeError"))
    result = registered_project_parser.save_active_registered_project(TEST_PROJECT_DATA)
    assert result is False
    assert "Type error during JSON serialization" in caplog.text


def test_clear_active_project_app_paths_os_error(mocker: MockerFixture, caplog) -> None:
    """Verify that clearing handles an OSError when initializing AppPaths."""
    # Arrange
    mocker.patch(
        "devildex.local_data_parse.registered_project_parser.AppPaths",
        side_effect=OSError("Test AppPaths OSError"),
    )
    registered_project_parser.clear_active_registered_project()
    assert "Error determining the path of the registration file" in caplog.text


def test_clear_active_project_unlink_os_error(
    mock_app_paths: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that clearing handles an OSError during file deletion."""
    mock_app_paths.write_text(json.dumps(TEST_PROJECT_DATA))
    mocker.patch.object(Path, "unlink", side_effect=OSError("Test unlink OSError"))
    registered_project_parser.clear_active_registered_project()
    assert "Error while removing the active project file" in caplog.text


def test_load_active_project_app_paths_os_error(mocker: MockerFixture, caplog) -> None:
    """Verify that loading handles an OSError when initializing AppPaths."""
    # Arrange
    mocker.patch(
        "devildex.local_data_parse.registered_project_parser.AppPaths",
        side_effect=OSError("Test AppPaths OSError"),
    )
    loaded_data = registered_project_parser.load_active_registered_project()
    assert loaded_data is None
    assert "Error determining the path of the registration file" in caplog.text


def test_load_active_project_no_registry_dir(
    tmp_path: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that loading handles the case: the registry directory doesn't exist."""
    mock_app_paths_class = mocker.patch(
        "devildex.local_data_parse.registered_project_parser.AppPaths"
    )
    mock_app_paths_instance = mock_app_paths_class.return_value
    mock_app_paths_instance.user_data_dir = tmp_path
    with caplog.at_level(logging.DEBUG):
        loaded_data = registered_project_parser.load_active_registered_project()
    assert loaded_data is None
    assert "Registration file path not determinable." in caplog.text
