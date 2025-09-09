"""Tests for the example.py utility script."""

import importlib
import logging
from unittest.mock import MagicMock

import pytest

from devildex.utils import example


def test_example_script_logs_correctly(
    mocker: MagicMock, cap_log: pytest.LogCaptureFixture
) -> None:
    """Verify that the example script runs and logs the expected messages.

    This test mocks the IsolatedVenvManager to avoid actual filesystem
    operations and reloads the module to trigger its execution.
    """
    # Arrange
    # 1. Create a mock for the venv_manager instance that is returned
    #    by the context manager's __enter__ method.
    mock_venv_manager_instance = MagicMock()
    mock_venv_manager_instance.python_executable = "/fake/venv/bin/python"
    mock_venv_manager_instance.pip_executable = "/fake/venv/bin/pip"

    # 2. Create a mock for the IsolatedVenvManager class itself.
    #    This mock needs to handle the context manager protocol (`with` statement).
    mock_venv_manager_class = MagicMock()
    mock_venv_manager_class.return_value.__enter__.return_value = (
        mock_venv_manager_instance
    )

    # 3. Patch the class within the 'example' module's namespace.
    mocker.patch("devildex.utils.venv_cm.IsolatedVenvManager", mock_venv_manager_class)

    # Act
    # The script's code runs on import. We must reload it to execute it
    # again for this test with our patch in place.
    with cap_log.at_level(logging.INFO):
        importlib.reload(example)

    # Assert
    # FIX: Check that the mock object itself was called, not the original class.
    mock_venv_manager_class.assert_called_once_with(project_name="mio_project")

    # Check the log messages produced by the script
    assert "Using Python da: /fake/venv/bin/python" in cap_log.text
    assert "Using pip da: /fake/venv/bin/pip" in cap_log.text
    assert "Environment virtual per mio_project removed." in cap_log.text
