"""Tests for the registered_project_parser module."""

import json
import logging
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.local_data_parse import registered_project_parser
from devildex.local_data_parse.registered_project_parser import RegisteredProjectData

# Sample data for testing
TEST_PROJECT_DATA: RegisteredProjectData = {
    "project_name": "MyTestProject",
    "project_path": "/fake/path/to/project",
    "python_executable": "/fake/venv/bin/python",
}


@pytest.fixture
def mock_app_paths(tmp_path: Path, mocker: MockerFixture) -> Path:
    """Mock AppPaths to use a temporary user_data_dir."""
    # The production code builds the path from `user_data_dir`.
    # We need to mock this attribute.
    mock_user_data_dir = tmp_path / "user_data"
    mock_user_data_dir.mkdir()

    # This is the final file path that the production code will construct.
    # We return it so the tests can assert against it.
    expected_file_path = (
        mock_user_data_dir
        / registered_project_parser.REGISTRY_SUBDIR
        / registered_project_parser.REGISTRATION_FILE_NAME
    )

    # FIX: The tests that write a file directly need the parent directory to exist.
    # The production code creates it, but the test setup doesn't.
    # Let's create it here to make the fixture more robust for all tests.
    expected_file_path.parent.mkdir(parents=True, exist_ok=True)

    mock_app_paths_class = mocker.patch(
        "devildex.local_data_parse.registered_project_parser.AppPaths"
    )
    mock_app_paths_instance = mock_app_paths_class.return_value
    mock_app_paths_instance.user_data_dir = mock_user_data_dir

    return expected_file_path


def test_save_and_load_active_project(mock_app_paths: Path) -> None:
    """Verify that project data can be saved to a JSON file and loaded back."""
    # Arrange: The fixture has already set up the temporary file path

    # Act: Save the data
    registered_project_parser.save_active_registered_project(TEST_PROJECT_DATA)

    # Assert: Check the file's content directly
    assert mock_app_paths.is_file()
    with open(mock_app_paths) as f:
        content_on_disk = json.load(f)
    assert content_on_disk == TEST_PROJECT_DATA

    # Act: Load the data back using the function
    loaded_data = registered_project_parser.load_active_registered_project()

    # Assert: Check the loaded data
    assert loaded_data is not None
    assert loaded_data["project_name"] == "MyTestProject"
    assert loaded_data == TEST_PROJECT_DATA


def test_load_active_project_file_not_found(mock_app_paths: Path) -> None:
    """Verify that loading returns None when the active project file does not exist."""
    # Arrange: The file does not exist by default in the temp path
    assert not mock_app_paths.exists()

    # Act
    loaded_data = registered_project_parser.load_active_registered_project()

    # Assert
    assert loaded_data is None


def test_load_active_project_invalid_json(mock_app_paths: Path, caplog) -> None:
    """Verify that loading returns None and logs an error for a corrupt JSON file."""
    # Arrange: Create a file with invalid (non-JSON) content
    mock_app_paths.write_text("this is not valid json {")
    assert mock_app_paths.is_file()

    # Act
    loaded_data = registered_project_parser.load_active_registered_project()

    # Assert
    assert loaded_data is None
    assert "Error decoding JSON from file" in caplog.text
    assert str(mock_app_paths) in caplog.text


def test_load_active_project_missing_required_keys(
    mock_app_paths: Path, caplog
) -> None:
    """Verify loading fails if the JSON is valid but missing required keys."""
    # Arrange: Data is missing the 'python_executable' key
    corrupt_data = {"project_name": "Incomplete", "project_path": "/path"}
    mock_app_paths.write_text(json.dumps(corrupt_data))

    # Act
    loaded_data = registered_project_parser.load_active_registered_project()

    # Assert
    assert loaded_data is None
    assert "Required key 'python_executable' missing or None" in caplog.text


def test_clear_active_registered_project(mock_app_paths: Path) -> None:
    """Verify that clearing the active project deletes the corresponding file."""
    # Arrange: Create the file first so we can test its deletion
    mock_app_paths.write_text(json.dumps(TEST_PROJECT_DATA))
    assert mock_app_paths.is_file()

    # Act
    registered_project_parser.clear_active_registered_project()

    # Assert
    assert not mock_app_paths.exists()


def test_clear_active_registered_project_file_not_exist(mock_app_paths: Path) -> None:
    """Verify that clearing does not raise an error if the file is already gone."""
    # Arrange: The file does not exist
    assert not mock_app_paths.exists()

    # Act & Assert: Should execute without raising an exception
    try:
        registered_project_parser.clear_active_registered_project()
    except Exception as e:
        pytest.fail(
            f"clear_active_registered_project raised an exception unexpectedly: {e}"
        )


def test_save_active_project_missing_required_keys(caplog) -> None:
    """Verify that saving fails if the input data is missing required keys."""
    # Arrange: Data is missing the 'project_path' key
    # We need to cast to RegisteredProjectData to satisfy the type checker,
    # even though the data is intentionally invalid for the test.
    invalid_data: RegisteredProjectData = {  # type: ignore
        "project_name": "Invalid",
        "python_executable": "/bin/python",
    }

    # Act
    result = registered_project_parser.save_active_registered_project(invalid_data)

    # Assert
    assert result is False
    assert "required key 'project_path' missing or None" in caplog.text


def test_load_active_project_invalid_path_in_json(mock_app_paths: Path, caplog) -> None:
    """Verify that loading handles an invalid path in the JSON file."""
    # Arrange: Create a file with an invalid path (e.g., contains null byte)
    invalid_path_data = {
        "project_name": "InvalidPathProject",
        "project_path": "/fake/path/to/project",
        "python_executable": "/fake/venv/bin/python\0",  # Invalid path
    }
    mock_app_paths.write_text(json.dumps(invalid_path_data))

    # Act
    loaded_data = registered_project_parser.load_active_registered_project()

    # Assert
    assert loaded_data is not None
    assert "Invalid path for 'python_executable'" in caplog.text


def test_load_active_project_os_error_on_open(
    mock_app_paths: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that loading handles an OSError when opening the file."""
    # Arrange
    mock_app_paths.write_text(json.dumps(TEST_PROJECT_DATA))
    mocker.patch.object(Path, "open", side_effect=OSError("Test OSError"))

    # Act
    loaded_data = registered_project_parser.load_active_registered_project()

    # Assert
    assert loaded_data is None
    assert "Unexpected error while parsing file" in caplog.text


def test_save_active_project_mkdir_os_error(mocker: MockerFixture, caplog) -> None:
    """Verify that saving handles an OSError during directory creation."""
    # Arrange
    mocker.patch.object(Path, "mkdir", side_effect=OSError("Test mkdir OSError"))

    # Act
    result = registered_project_parser.save_active_registered_project(TEST_PROJECT_DATA)

    # Assert
    assert result is False
    assert "Error determining or creating the path" in caplog.text


def test_save_active_project_open_os_error(
    mock_app_paths: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that saving handles an OSError when opening the file for writing."""
    # Arrange
    mocker.patch.object(Path, "open", side_effect=OSError("Test open OSError"))

    # Act
    result = registered_project_parser.save_active_registered_project(TEST_PROJECT_DATA)

    # Assert
    assert result is False
    assert "I/O error while saving the active project" in caplog.text


def test_save_active_project_json_type_error(
    mock_app_paths: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that saving handles a TypeError during JSON serialization."""
    # Arrange
    mocker.patch("json.dump", side_effect=TypeError("Test TypeError"))

    # Act
    result = registered_project_parser.save_active_registered_project(TEST_PROJECT_DATA)

    # Assert
    assert result is False
    assert "Type error during JSON serialization" in caplog.text


def test_clear_active_project_app_paths_os_error(mocker: MockerFixture, caplog) -> None:
    """Verify that clearing handles an OSError when initializing AppPaths."""
    # Arrange
    mocker.patch(
        "devildex.local_data_parse.registered_project_parser.AppPaths",
        side_effect=OSError("Test AppPaths OSError"),
    )

    # Act
    registered_project_parser.clear_active_registered_project()

    # Assert
    assert "Error determining the path of the registration file" in caplog.text


def test_clear_active_project_unlink_os_error(
    mock_app_paths: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that clearing handles an OSError during file deletion."""
    # Arrange
    mock_app_paths.write_text(json.dumps(TEST_PROJECT_DATA))
    mocker.patch.object(Path, "unlink", side_effect=OSError("Test unlink OSError"))

    # Act
    registered_project_parser.clear_active_registered_project()

    # Assert
    assert "Error while removing the active project file" in caplog.text


def test_load_active_project_app_paths_os_error(mocker: MockerFixture, caplog) -> None:
    """Verify that loading handles an OSError when initializing AppPaths."""
    # Arrange
    mocker.patch(
        "devildex.local_data_parse.registered_project_parser.AppPaths",
        side_effect=OSError("Test AppPaths OSError"),
    )

    # Act
    loaded_data = registered_project_parser.load_active_registered_project()

    # Assert
    assert loaded_data is None
    assert "Error determining the path of the registration file" in caplog.text


def test_load_active_project_no_registry_dir(
    tmp_path: Path, mocker: MockerFixture, caplog
) -> None:
    """Verify that loading handles the case where the registry directory doesn't exist."""
    # Arrange
    # Mock AppPaths to point to our temporary directory
    mock_app_paths_class = mocker.patch(
        "devildex.local_data_parse.registered_project_parser.AppPaths"
    )
    mock_app_paths_instance = mock_app_paths_class.return_value
    mock_app_paths_instance.user_data_dir = tmp_path

    # The registry subdir does NOT exist yet inside tmp_path

    # Act
    with caplog.at_level(logging.DEBUG):
        loaded_data = registered_project_parser.load_active_registered_project()

    # Assert
    assert loaded_data is None
    assert "Registration file path not determinable." in caplog.text
