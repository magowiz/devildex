"""Tests for the example.py utility script."""

from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from devildex.utils import example


def test_example_script_logs_correctly(
    mocker: MockerFixture
) -> None:
    """Verify that the example script runs and logs the expected messages."""
    mock_venv_manager_instance = MagicMock()
    mock_venv_manager_instance.python_executable = "/fake/venv/bin/python"
    mock_venv_manager_instance.pip_executable = "/fake/venv/bin/pip"
    mock_venv_manager_class = MagicMock()
    mock_venv_manager_class.return_value.__enter__.return_value = (
        mock_venv_manager_instance
    )
    mocker.patch("devildex.utils.example.IsolatedVenvManager", mock_venv_manager_class)

    mock_logger = mocker.patch("devildex.utils.example.logger")

    example.main()

    mock_venv_manager_class.assert_called_once_with(project_name="mio_project")
    mock_logger.info.assert_any_call("Using Python da: %s", "/fake/venv/bin/python")
    mock_logger.info.assert_any_call("Using pip da: %s", "/fake/venv/bin/pip")
    mock_logger.info.assert_any_call("Environment virtual per mio_project removed.")
