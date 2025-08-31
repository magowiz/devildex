"""Tests for the _external_scanner_script module."""

import json
from unittest.mock import MagicMock, mock_open, patch

# The script starts with an underscore, so we import it this way
from devildex.local_data_parse import _external_scanner_script as scanner_script


@patch("devildex.local_data_parse._external_scanner_script.sys.exit")
@patch("devildex.local_data_parse._external_scanner_script._main_write_json")
@patch("importlib.metadata.distributions")
def test_main_success(mock_distributions, mock_write_json, mock_exit) -> None:
    """Verify that the main function generates correct JSON and exits cleanly."""
    # Arrange
    # Mock sys.argv to simulate command-line arguments
    with patch("sys.argv", ["_external_scanner_script.py", "/fake/output.json"]):

        # Mock for 'requests'
        mock_dist1 = MagicMock()
        mock_dist1.name = "requests"
        mock_dist1.version = "2.25.1"
        mock_dist1.metadata = MagicMock()
        mock_dist1.metadata.get.return_value = "HTTP for Humans."
        mock_dist1.metadata.get_all.return_value = [
            "Source, https://github.com/psf/requests"
        ]

        # Mock for 'pytest'
        mock_dist2 = MagicMock()
        mock_dist2.name = "pytest"
        mock_dist2.version = "7.0.0"
        mock_dist2.metadata = MagicMock()
        mock_dist2.metadata.get.return_value = ""
        mock_dist2.metadata.get_all.return_value = [
            "Homepage, https://pytest.org",
            "Documentation, https://docs.pytest.org",
        ]

        mock_distributions.return_value = [mock_dist1, mock_dist2]

        # Act
        scanner_script.main()

    # Assert
    # 1. Check that the write function was called
    mock_write_json.assert_called_once()

    # 2. Check the data passed to the write function
    call_args = mock_write_json.call_args[0]
    written_data = call_args[1]

    assert isinstance(written_data, list)
    assert len(written_data) == 2

    requests_data = next(p for p in written_data if p["name"] == "requests")
    assert requests_data["version"] == "2.25.1"
    assert requests_data["summary"] == "HTTP for Humans."
    assert requests_data["project_urls"] == {
        "Source": "https://github.com/psf/requests"
    }

    pytest_data = next(p for p in written_data if p["name"] == "pytest")
    assert pytest_data["version"] == "7.0.0"
    assert pytest_data["summary"] == ""
    assert pytest_data["project_urls"] == {
        "Homepage": "https://pytest.org",
        "Documentation": "https://docs.pytest.org",
    }


@patch("devildex.local_data_parse._external_scanner_script.sys.exit")
@patch("devildex.local_data_parse._external_scanner_script.logger.exception")
@patch("importlib.metadata.distributions")
def test_main_discovery_exception(
    mock_distributions, mock_log_exception, mock_exit
) -> None:
    """Verify that the script exits with 1 on a discovery error."""
    with patch("sys.argv", ["_external_scanner_script.py", "/fake/output.json"]):
        mock_distributions.side_effect = Exception("Discovery failed")
        # Act
        scanner_script.main()

    # Assert
    mock_exit.assert_called_once_with(1)
    mock_log_exception.assert_called_once()
    log_call_args = mock_log_exception.call_args[0][0]
    error_payload = json.loads(log_call_args)
    assert "error" in error_payload
    assert "Discovery failed" in error_payload["error"]


@patch("devildex.local_data_parse._external_scanner_script.sys.exit")
@patch("devildex.local_data_parse._external_scanner_script.logger.debug")
def test_args_checker_insufficient_args(mock_logger_debug, mock_exit) -> None:
    """Verify _args_checker exits if not enough arguments are provided."""
    with patch("sys.argv", ["_external_scanner_script.py"]):  # Only one arg
        scanner_script._args_checker()
    mock_logger_debug.assert_called_once_with(
        "DEBUG_HELPER: Error: Output file path not provided as argument."
    )
    mock_exit.assert_called_once_with(2)


@patch("devildex.local_data_parse._external_scanner_script.sys.exit")
@patch("devildex.local_data_parse._external_scanner_script.logger.debug")
@patch("builtins.open", side_effect=OSError("Disk full"))
def test_main_write_json_os_error(mock_open, mock_logger_debug, mock_exit) -> None:
    """Verify _main_write_json handles OSError during file writing."""
    scanner_script._main_write_json("/fake/output.json", [{"name": "test"}])
    mock_logger_debug.assert_called_once()
    assert "IOError writing to output file" in mock_logger_debug.call_args[0][0]
    mock_exit.assert_called_once_with(3)


@patch("devildex.local_data_parse._external_scanner_script.sys.exit")
@patch("devildex.local_data_parse._external_scanner_script.logger.debug")
@patch("json.dump", side_effect=TypeError("Object not serializable"))
@patch("builtins.open", new_callable=mock_open)
def test_main_write_json_json_error(
    mock_open, mock_json_dump, mock_logger_debug, mock_exit
) -> None:
    """Verify _main_write_json handles JSON serialization errors."""
    scanner_script._main_write_json(
        "/fake/output.json", [object()]
    )  # object() is not JSON serializable
    mock_logger_debug.assert_called_once()
    assert (
        "Exception during final JSON dump/file write"
        in mock_logger_debug.call_args[0][0]
    )
    mock_exit.assert_called_once_with(1)


@patch("devildex.local_data_parse._external_scanner_script.sys.exit")
@patch("devildex.local_data_parse._external_scanner_script.logger.debug")
@patch("builtins.open", new_callable=mock_open)
@patch("json.dump")
def test_main_write_json_success(
    mock_json_dump, mock_open, mock_logger_debug, mock_exit
) -> None:
    """Verify _main_write_json successfully writes JSON and exits."""
    output_file_path = "/fake/output.json"
    package_list = [{"name": "test", "version": "1.0"}]

    scanner_script._main_write_json(output_file_path, package_list)

    mock_open.assert_called_once_with(output_file_path, "w", encoding="utf-8")
    mock_json_dump.assert_called_once_with(package_list, mock_open(), indent=2)
    mock_logger_debug.assert_called_once_with(
        f"DEBUG_HELPER: Successfully wrote JSON to {output_file_path}"
    )
    mock_exit.assert_called_once_with(0)


@patch("devildex.local_data_parse._external_scanner_script.sys.exit")
@patch(
    "devildex.local_data_parse._external_scanner_script.logger.exception"
)  # Patch logger.exception
@patch("devildex.local_data_parse._external_scanner_script._main_write_json")
@patch("importlib.metadata.distributions")
def test_main_project_url_attribute_error(
    mock_distributions, mock_write_json, mock_log_exception, mock_exit
) -> None:
    """Verify main handles AttributeError in project_urls parsing."""
    with patch("sys.argv", ["_external_scanner_script.py", "/fake/output.json"]):
        mock_dist = MagicMock()
        mock_dist.name = "test_package"
        mock_dist.version = "1.0.0"
        mock_dist.metadata = MagicMock()
        mock_dist.metadata.get.return_value = ""

        # Simulate an AttributeError during iteration of Project-URL entries
        mock_project_urls = MagicMock()
        mock_project_urls.__iter__.side_effect = AttributeError("Mocked AttributeError")
        mock_dist.metadata.get_all.return_value = mock_project_urls

        mock_distributions.return_value = [mock_dist]

        scanner_script.main()

    mock_exit.assert_called_once_with(1)
    # Ensure _main_write_json was not called with valid data
    mock_write_json.assert_not_called()
    mock_log_exception.assert_called_once()
    log_call_args = mock_log_exception.call_args[0][0]
    assert "Error in _external_scanner_script.py" in log_call_args
