"""
Tests for the deletion helper methods within the DevilDexApp class.
"""

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.constants import NOT_AVAILABLE_BTN_LABEL
from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture) -> DevilDexApp:
    """
    Provides a DevilDexApp instance for testing without a running event loop.
    """
    # Prevent the real wx.App from initializing
    mocker.patch("wx.App.__init__", return_value=None)
    # Ensure log handler calls AppendText directly instead of via wx.CallAfter
    mocker.patch("wx.IsMainThread", return_value=True)

    # Mock the core dependency
    mock_core = mocker.MagicMock(name="DevilDexCore")

    # Create the app instance with the mocked core
    app_instance = DevilDexApp(core=mock_core)

    # Attach mocks for UI collaborators
    app_instance.log_text_ctrl = mocker.MagicMock(name="LogTextCtrl")
    mocker.patch("wx.MessageBox")

    # Mock the grid and its panel
    mock_grid = mocker.MagicMock(spec=wx.grid.Grid)
    app_instance.grid_panel = mocker.MagicMock()
    app_instance.grid_panel.grid = mock_grid

    # Set up some initial state for the tests
    app_instance.docset_status_col_grid_idx = 5  # Example column index
    app_instance.selected_row_index = 0
    app_instance.current_grid_source_data = [
        {
            "id": "pkg-123",
            "name": "test-package",
            "docset_status": "Available",
            "docset_path": "/path/to/be/deleted",
        }
    ]

    # FIX: Initialize the log handler so it's connected to the mock text control
    app_instance.init_log()

    return app_instance


def test_update_grid_after_delete(app: DevilDexApp):
    """Verify that _update_grid_after_delete correctly updates data and UI."""
    # Act
    app._update_grid_after_delete()

    # Assert
    # Check in-memory data source
    updated_data = app.current_grid_source_data[0]
    assert updated_data["docset_status"] == NOT_AVAILABLE_BTN_LABEL
    assert "docset_path" not in updated_data

    # Check grid UI calls
    app.grid_panel.grid.SetCellValue.assert_called_once_with(
        0, 5, NOT_AVAILABLE_BTN_LABEL
    )
    app.grid_panel.grid.ForceRefresh.assert_called_once()


def test_handle_delete_success(app: DevilDexApp, mocker: MockerFixture):
    """Verify that _handle_delete_success logs, shows a message, and updates the grid."""
    # Arrange
    mock_update_grid = mocker.patch.object(app, "_update_grid_after_delete")
    package_name = "test-package"

    # Act
    app._handle_delete_success(package_name)

    # Assert
    # Check logging
    app.log_text_ctrl.AppendText.assert_called_once()
    assert "Successfully deleted" in app.log_text_ctrl.AppendText.call_args[0][0]

    # Check user message
    wx.MessageBox.assert_called_once()
    assert "has been deleted" in wx.MessageBox.call_args[0][0]

    # Check that it calls the grid update helper
    mock_update_grid.assert_called_once()


def test_handle_delete_failure(app: DevilDexApp):
    """Verify that _handle_delete_failure logs and shows an error message."""
    # Arrange
    package_name = "test-package"
    error_message = "Disk is full"

    # Act
    app._handle_delete_failure(package_name, error_message)

    # Assert
    # Check logging
    app.log_text_ctrl.AppendText.assert_called_once()
    log_call_args = app.log_text_ctrl.AppendText.call_args[0][0]
    assert "failed to delete" in log_call_args
    assert error_message in log_call_args

    # Check user message
    wx.MessageBox.assert_called_once()
    msg_box_args = wx.MessageBox.call_args[0]
    assert "Could not delete" in msg_box_args[0]
    assert error_message in msg_box_args[0]
