"""
Tests for the regeneration logic within the DevilDexApp class.

This file is separate to avoid breaking the main test file for UI logic.
"""

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture) -> DevilDexApp:
    """
    Provides a DevilDexApp instance for testing without a running event loop.
    """
    # Prevent the real wx.App from initializing
    mocker.patch("wx.App.__init__", return_value=None)

    # Mock the core dependency
    mock_core = mocker.MagicMock(name="DevilDexCore")

    # Create the app instance with the mocked core
    app_instance = DevilDexApp(core=mock_core)

    # Attach mocks for UI collaborators
    app_instance.actions_panel = mocker.MagicMock(name="ActionsPanel")
    app_instance.log_text_ctrl = mocker.MagicMock(name="LogTextCtrl")
    # Mock MessageBox to prevent dialogs from popping up during tests
    mocker.patch("wx.MessageBox")

    return app_instance


# --- Tests for on_regenerate_docset ---


def test_on_regenerate_docset_success(app: DevilDexApp, mocker: MockerFixture):
    """Verify it calls delete and then generate in order."""
    # Arrange
    app.selected_row_index = 0
    mocker.patch.object(app, "get_selected_row", return_value={"name": "test-package"})

    # Mock the chained methods
    mock_delete = mocker.patch.object(app, "on_delete_docset")
    mock_generate = mocker.patch.object(app, "on_generate_docset")

    # Use a manager to check the call order
    manager = mocker.Mock()
    manager.attach_mock(mock_delete, "delete")
    manager.attach_mock(mock_generate, "generate")

    # Act
    app.on_regenerate_docset(event=mocker.MagicMock())

    # Assert
    # Check that the methods were called in the correct sequence
    expected_calls = [
        mocker.call.delete(event=None),
        mocker.call.generate(event=None),
    ]
    manager.assert_has_calls(expected_calls)


def test_on_regenerate_docset_no_selection(app: DevilDexApp, mocker: MockerFixture):
    """Verify it shows a message box if no package is selected."""
    # Arrange
    app.selected_row_index = None
    mock_delete = mocker.patch.object(app, "on_delete_docset")
    mock_generate = mocker.patch.object(app, "on_generate_docset")

    # Act
    app.on_regenerate_docset(event=mocker.MagicMock())

    # Assert
    wx.MessageBox.assert_called_once()
    assert "Please select a package" in wx.MessageBox.call_args[0][0]
    mock_delete.assert_not_called()
    mock_generate.assert_not_called()
