"""Extended tests for the external_venv_scanner module."""

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from devildex.local_data_parse.external_venv_scanner import ExternalVenvScanner


def test_init_invalid_python_path(caplog: pytest.LogCaptureFixture) -> None:
    """Verify that a warning is logged for an invalid python executable path."""
    invalid_path = "/path/to/non/existent/python"
    with caplog.at_level(logging.WARNING):
        ExternalVenvScanner(python_executable_path=invalid_path)
    assert "doesn't seem to be a valid file" in caplog.text


def test_init_script_content_not_loaded(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an error is logged if the helper script content cannot be loaded."""
    # Arrange
    mocker.patch(
        "devildex.local_data_parse.external_venv_scanner.ExternalVenvScanner._load_helper_script_content",
        return_value=None,
    )
    mock_path = mocker.patch("pathlib.Path")
    mock_path.return_value.is_file.return_value = True
    with caplog.at_level(logging.ERROR):
        ExternalVenvScanner(python_executable_path="/fake/path")
    assert "script helper content not loaded" in caplog.text


def test_load_helper_script_content_file_not_found(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an error is logged when the helper script is not found."""
    mocker.patch("importlib.resources.files", side_effect=FileNotFoundError)
    with caplog.at_level(logging.ERROR):
        result = ExternalVenvScanner._load_helper_script_content()
    assert result is None
    assert "non trovato (FileNotFoundError)" in caplog.text


def test_load_helper_script_content_os_error(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an error is logged on OSError while loading the helper script."""
    mocker.patch("importlib.resources.files", side_effect=OSError)
    with caplog.at_level(logging.ERROR):
        result = ExternalVenvScanner._load_helper_script_content()
    assert result is None
    assert "Error during loading helper script" in caplog.text


def test_execute_helper_script_no_content(caplog: pytest.LogCaptureFixture) -> None:
    """Verify error logging when script content is not loaded."""
    scanner = ExternalVenvScanner(python_executable_path="/fake/path")
    scanner.script_content = None
    with caplog.at_level(logging.ERROR):
        result = scanner._execute_helper_script("any/path")
    assert result is None
    assert "Cannot execute helper script: script content not loaded." in caplog.text


def test_execute_helper_script_timeout(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that a TimeoutExpired exception is handled correctly."""
    mocker.patch(
        "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="", timeout=1)
    )
    scanner = ExternalVenvScanner(python_executable_path="/fake/path")
    with caplog.at_level(logging.ERROR):
        result = scanner._execute_helper_script("any/path")
    assert result is None
    assert "Timeout Expired during the execution of the helper script" in caplog.text


def test_execute_helper_script_file_not_found(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that a FileNotFoundError is handled correctly."""
    mocker.patch("subprocess.run", side_effect=FileNotFoundError)
    scanner = ExternalVenvScanner(python_executable_path="/fake/path")
    with caplog.at_level(logging.ERROR):
        result = scanner._execute_helper_script("any/path")
    assert result is None
    assert "Python executable '/fake/path' not found" in caplog.text


def test_execute_helper_script_os_error(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an OSError is handled correctly."""
    mocker.patch("subprocess.run", side_effect=OSError)
    scanner = ExternalVenvScanner(python_executable_path="/fake/path")
    with caplog.at_level(logging.ERROR):
        result = scanner._execute_helper_script("any/path")
    assert result is None
    assert "OS error during execution of the helper script" in caplog.text


def test_parse_and_convert_scan_data_with_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that an error in the JSON output is handled correctly."""
    json_data = '{"error": "Something went wrong", "traceback": "Traceback..."}'
    with caplog.at_level(logging.ERROR):
        result = ExternalVenvScanner._parse_and_convert_scan_data(json_data, "test")
    assert result is None
    assert "The helper script reported an error" in caplog.text
    assert "Traceback from helper script" in caplog.text


def test_parse_and_convert_scan_data_not_a_list(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that non-list JSON data is handled correctly."""
    json_data = '{"key": "value"}'
    with caplog.at_level(logging.ERROR):
        result = ExternalVenvScanner._parse_and_convert_scan_data(json_data, "test")
    assert result is None
    assert "Unexpected output format" in caplog.text


def test_parse_and_convert_scan_data_item_not_a_dict(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that a non-dict element in the JSON list is handled correctly."""
    json_data = '[{"name": "pkg1"}, "not-a-dict"]'
    with caplog.at_level(logging.WARNING):
        result = ExternalVenvScanner._parse_and_convert_scan_data(json_data, "test")
    assert result is not None
    assert len(result) == 1
    assert "Non-dictionary element found" in caplog.text


def test_parse_and_convert_scan_data_package_details_error(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an error during PackageDetails conversion is handled."""
    mocker.patch(
        "devildex.database.models.PackageDetails.from_dict",
        side_effect=Exception("Conversion error"),
    )
    json_data = '[{"name": "pkg1"}]'
    with caplog.at_level(logging.WARNING):
        result = ExternalVenvScanner._parse_and_convert_scan_data(json_data, "test")
    assert result == []
    assert "Error converting JSON package data" in caplog.text


def test_parse_and_convert_scan_data_json_decode_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that a JSONDecodeError is handled correctly."""
    json_data = "invalid-json"
    with caplog.at_level(logging.ERROR):
        result = ExternalVenvScanner._parse_and_convert_scan_data(json_data, "test")
    assert result is None
    assert "Error decoding JSON output" in caplog.text


def test_read_and_process_output_file_os_error(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an OSError during file reading is handled."""
    mock_path_instance = mocker.MagicMock(spec=Path)
    mock_path_instance.is_file.return_value = True
    mock_path_instance.stat.return_value.st_size = 100
    mock_path_instance.read_text.side_effect = OSError("Read error")
    scanner = ExternalVenvScanner(python_executable_path="/fake/path")
    with caplog.at_level(logging.ERROR):
        result = scanner._read_and_process_output_file(mock_path_instance)
    assert result is None
    assert "Error reading temporary output file" in caplog.text


def test_scan_packages_no_script_content(caplog: pytest.LogCaptureFixture) -> None:
    """Verify that an error is logged if the script content is not loaded."""
    scanner = ExternalVenvScanner(python_executable_path="/fake/path")
    scanner.script_content = None
    with caplog.at_level(logging.ERROR):
        result = scanner.scan_packages()
    assert result is None
    assert "Helper script content not loaded. Cannot scan packages." in caplog.text


def test_scan_packages_unlink_os_error(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an OSError during temporary file cleanup is handled."""
    mocker.patch("subprocess.run").return_value = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    mock_temp_file = mocker.patch("tempfile.NamedTemporaryFile")
    temp_file_path = Path("/fake/temp_file.json")
    mock_file_handle = MagicMock()
    mock_file_handle.__enter__.return_value.name = str(temp_file_path)
    mock_temp_file.return_value = mock_file_handle
    mocker.patch.object(Path, "unlink", side_effect=OSError("Unlink error"))
    mocker.patch.object(Path, "is_file", return_value=True)
    mocker.patch.object(Path, "stat").return_value.st_size = 2
    mocker.patch.object(Path, "read_text", return_value="[]")
    scanner = ExternalVenvScanner(
        python_executable_path=str(temp_file_path.parent / "python")
    )
    with caplog.at_level(logging.WARNING):
        scanner.scan_packages()
    assert "Could not delete temporary output file" in caplog.text


def test_execute_helper_script_with_stdout(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that stdout from the helper script is logged."""
    mocker.patch("subprocess.run").return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="Some output"
    )
    scanner = ExternalVenvScanner(python_executable_path="/usr/bin/python3")

    # Act
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        scanner._execute_helper_script("any/path")

    # Assert
    assert "STDOUT (diagnostic) of helper script" in caplog.text


def test_load_helper_script_content_not_a_file(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an error is logged when the helper script path is not a file."""
    # Arrange
    mock_path = mocker.MagicMock()
    mock_path.__truediv__.return_value.is_file.return_value = False
    mocker.patch("importlib.resources.files", return_value=mock_path)

    # Act
    with caplog.at_level(logging.ERROR):
        result = ExternalVenvScanner._load_helper_script_content()

    # Assert
    assert result is None
    assert "not found as file" in caplog.text


def test_read_and_process_output_file_empty_file(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an empty file is handled correctly."""
    # Arrange
    mock_path_instance = mocker.MagicMock(spec=Path)
    mock_path_instance.is_file.return_value = True
    mock_path_instance.stat.return_value.st_size = 100
    mock_path_instance.read_text.return_value = " "
    scanner = ExternalVenvScanner(python_executable_path="/fake/path")

    # Act
    with caplog.at_level(logging.INFO):
        result = scanner._read_and_process_output_file(mock_path_instance)

    # Assert
    assert result == []
    assert "No JSON content" in caplog.text


def test_scan_packages_logs_completion(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that a successful scan logs the completion message."""
    # Arrange
    mocker.patch("subprocess.run").return_value = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    mock_temp_file = mocker.patch("tempfile.NamedTemporaryFile")
    temp_file_path = Path("/fake/temp_file.json")
    mock_file_handle = MagicMock()
    mock_file_handle.__enter__.return_value.name = str(temp_file_path)
    mock_temp_file.return_value = mock_file_handle

    mocker.patch.object(Path, "is_file", return_value=True)
    mocker.patch.object(Path, "stat").return_value.st_size = 2
    mocker.patch.object(
        Path, "read_text", return_value='[{"name": "requests", "version": "2.25.1"}] '
    )

    scanner = ExternalVenvScanner(
        python_executable_path=str(temp_file_path.parent / "python")
    )

    # Act
    with caplog.at_level(logging.DEBUG):
        scanner.scan_packages()

    # Assert
    assert "Scan complete" in caplog.text
