"""Tests for the example.py utility script."""

import importlib
import logging
from unittest.mock import MagicMock

import pytest

from devildex.utils import example


def test_example_script_logs_correctly(
    mocker: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that the example script runs and logs the expected messages.

    This test mocks the IsolatedVenvManager to avoid actual filesystem
    operations and reloads the module to trigger its execution.
    """
    mock_venv_manager_instance = MagicMock()
    mock_venv_manager_instance.python_executable = "/fake/venv/bin/python"
    mock_venv_manager_instance.pip_executable = "/fake/venv/bin/pip"
    mock_venv_manager_class = MagicMock()
    mock_venv_manager_class.return_value.__enter__.return_value = (
        mock_venv_manager_instance
    )
    mocker.patch("devildex.utils.venv_cm.IsolatedVenvManager", mock_venv_manager_class)
    with caplog.at_level(logging.INFO):
        importlib.reload(example)
    mock_venv_manager_class.assert_called_once_with(project_name="mio_project")
    assert "Using Python da: /fake/venv/bin/python" in caplog.text
    assert "Using pip da: /fake/venv/bin/pip" in caplog.text
    assert "Environment virtual per mio_project removed." in caplog.text
