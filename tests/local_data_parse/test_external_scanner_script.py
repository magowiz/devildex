"""Tests for the _external_scanner_script module."""

import json
from unittest.mock import MagicMock, patch

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
