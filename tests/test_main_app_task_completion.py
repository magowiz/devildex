"""Tests for the task completion callback logic within the DevilDexApp class."""

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.constants import AVAILABLE_BTN_LABEL, ERROR_BTN_LABEL
from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture) -> DevilDexApp:
    """Provide a DevilDexApp instance for testing without a running event loop."""
    mocker.patch("wx.App.__init__", return_value=None)
    mock_core = mocker.MagicMock(name="DevilDexCore")
    app_instance = DevilDexApp(core=mock_core)
    app_instance.log_text_ctrl = mocker.MagicMock(name="LogTextCtrl")
    mocker.patch("wx.MessageBox")
    mock_grid = mocker.MagicMock(spec=wx.grid.Grid)
    mock_grid.GetNumberRows.return_value = 1
    app_instance.grid_panel = mocker.MagicMock()
    app_instance.grid_panel.grid = mock_grid
    app_instance.docset_status_col_grid_idx = 5
    app_instance.current_grid_source_data = [{"id": "pkg-123", "name": "test-package"}]
    return app_instance


def test_on_generation_complete_success(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify UI updates correctly on a successful generation."""
    row_to_update = 0
    success_path = "/fake/path/to/docset"
    app._on_generation_complete_from_manager(
        success=True,
        message=success_path,
        package_name="test-package",
        package_id="pkg-123",
        row_idx_to_update=row_to_update,
    )
    app.grid_panel.grid.SetCellValue.assert_called_once_with(
        row_to_update, app.docset_status_col_grid_idx, AVAILABLE_BTN_LABEL
    )
    app.grid_panel.grid.ForceRefresh.assert_called_once()
    assert (
        app.current_grid_source_data[row_to_update]["docset_status"]
        == AVAILABLE_BTN_LABEL
    )
    assert app.current_grid_source_data[row_to_update]["docset_path"] == success_path
    app.log_text_ctrl.AppendText.assert_called_once()
    assert "SUCCESS" in app.log_text_ctrl.AppendText.call_args[0][0]
    wx.MessageBox.assert_not_called()


def test_on_generation_complete_failure(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify UI updates correctly on a failed generation."""
    row_to_update = 0
    app.current_grid_source_data[row_to_update]["docset_path"] = "/old/path"
    app._on_generation_complete_from_manager(
        success=False,
        message="Something went wrong",
        package_name="test-package",
        package_id="pkg-123",
        row_idx_to_update=row_to_update,
    )
    app.grid_panel.grid.SetCellValue.assert_called_once_with(
        row_to_update, app.docset_status_col_grid_idx, ERROR_BTN_LABEL
    )
    app.grid_panel.grid.ForceRefresh.assert_called_once()
    assert (
        app.current_grid_source_data[row_to_update]["docset_status"] == ERROR_BTN_LABEL
    )
    assert "docset_path" not in app.current_grid_source_data[row_to_update]
    app.log_text_ctrl.AppendText.assert_called_once()
    assert "ERROR" in app.log_text_ctrl.AppendText.call_args[0][0]
    wx.MessageBox.assert_called_once()
    assert "Error during generation" in wx.MessageBox.call_args[0][0]
