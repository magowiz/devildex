"""Tests for the deletion helper methods within the DevilDexApp class."""

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.constants import NOT_AVAILABLE_BTN_LABEL
from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture) -> DevilDexApp:
    """Provide a DevilDexApp instance for testing without a running event loop."""
    mocker.patch("wx.App.__init__", return_value=None)
    mocker.patch("wx.IsMainThread", return_value=True)
    mock_core = mocker.MagicMock(name="DevilDexCore")
    app_instance = DevilDexApp(core=mock_core)
    app_instance.log_text_ctrl = mocker.MagicMock(name="LogTextCtrl")
    mocker.patch("wx.MessageBox")
    mock_grid = mocker.MagicMock(spec=wx.grid.Grid)
    app_instance.grid_panel = mocker.MagicMock()
    app_instance.grid_panel.grid = mock_grid
    app_instance.docset_status_col_grid_idx = 5
    app_instance.selected_row_index = 0
    app_instance.current_grid_source_data = [
        {
            "id": "pkg-123",
            "name": "test-package",
            "docset_status": "Available",
            "docset_path": "/path/to/be/deleted",
        }
    ]
    app_instance.init_log()

    return app_instance


def test_update_grid_after_delete(app: DevilDexApp) -> None:
    """Verify that _update_grid_after_delete correctly updates data and UI."""
    app._update_grid_after_delete()
    updated_data = app.current_grid_source_data[0]
    assert updated_data["docset_status"] == NOT_AVAILABLE_BTN_LABEL
    assert "docset_path" not in updated_data
    app.grid_panel.grid.SetCellValue.assert_called_once_with(
        0, 5, NOT_AVAILABLE_BTN_LABEL
    )
    app.grid_panel.grid.ForceRefresh.assert_called_once()


def test_handle_delete_success(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify that _handle_delete_success shows a message, and updates the grid."""
    mock_update_grid = mocker.patch.object(app, "_update_grid_after_delete")
    package_name = "test-package"
    
    mock_logger = mocker.patch("devildex.main.logger")
    
    app._handle_delete_success(package_name)

    mock_logger.info.assert_called_once_with(
        f"GUI: Successfully deleted docset for '{package_name}'."
    )
    wx.MessageBox.assert_called_once()
    assert "has been deleted" in wx.MessageBox.call_args[0][0]
    mock_update_grid.assert_called_once()


def test_handle_delete_failure(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify that _handle_delete_failure logs and shows an error message."""
    package_name = "test-package"
    error_message = "Disk is full"
    
    mock_logger = mocker.patch("devildex.main.logger")
    
    app._handle_delete_failure(package_name, error_message)
    
    mock_logger.error.assert_called_once_with(
        f"GUI: Core failed to delete docset for '{package_name}'. Reason: {error_message}"
    )
    wx.MessageBox.assert_called_once()
    msg_box_args = wx.MessageBox.call_args[0]
    assert "Could not delete" in msg_box_args[0]
    assert error_message in msg_box_args[0]
