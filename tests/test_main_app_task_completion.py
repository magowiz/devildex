"""Tests for the task completion callback logic within the DevilDexApp class."""

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.constants import AVAILABLE_BTN_LABEL, ERROR_BTN_LABEL
from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture) -> DevilDexApp:
    """Provide a DevilDexApp instance for testing without a running event loop."""
    # Prevent the real wx.App from initializing
    mocker.patch("wx.App.__init__", return_value=None)

    # Mock the core dependency
    mock_core = mocker.MagicMock(name="DevilDexCore")

    # Create the app instance with the mocked core
    app_instance = DevilDexApp(core=mock_core)

    # Attach mocks for UI collaborators
    app_instance.log_text_ctrl = mocker.MagicMock(name="LogTextCtrl")
    mocker.patch("wx.MessageBox")

    # Mock the grid and its panel
    mock_grid = mocker.MagicMock(spec=wx.grid.Grid)
    mock_grid.GetNumberRows.return_value = 1
    app_instance.grid_panel = mocker.MagicMock()
    app_instance.grid_panel.grid = mock_grid

    # Set up some initial state
    app_instance.docset_status_col_grid_idx = 5  # Example column index
    app_instance.current_grid_source_data = [{"id": "pkg-123", "name": "test-package"}]

    return app_instance


def test_on_generation_complete_success(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify UI updates correctly on a successful generation."""
    # Arrange
    row_to_update = 0
    success_path = "/fake/path/to/docset"

    # Act
    app._on_generation_complete_from_manager(
        success=True,
        message=success_path,
        package_name="test-package",
        package_id="pkg-123",
        row_idx_to_update=row_to_update,
    )

    # Assert
    # Check grid update
    app.grid_panel.grid.SetCellValue.assert_called_once_with(
        row_to_update, app.docset_status_col_grid_idx, AVAILABLE_BTN_LABEL
    )
    app.grid_panel.grid.ForceRefresh.assert_called_once()

    # Check data source update
    assert (
        app.current_grid_source_data[row_to_update]["docset_status"]
        == AVAILABLE_BTN_LABEL
    )
    assert app.current_grid_source_data[row_to_update]["docset_path"] == success_path

    # Check logging and user feedback
    app.log_text_ctrl.AppendText.assert_called_once()
    assert "SUCCESS" in app.log_text_ctrl.AppendText.call_args[0][0]
    wx.MessageBox.assert_not_called()


def test_on_generation_complete_failure(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify UI updates correctly on a failed generation."""
    # Arrange
    row_to_update = 0
    # Pre-populate a path to ensure it gets removed on failure
    app.current_grid_source_data[row_to_update]["docset_path"] = "/old/path"

    # Act
    app._on_generation_complete_from_manager(
        success=False,
        message="Something went wrong",
        package_name="test-package",
        package_id="pkg-123",
        row_idx_to_update=row_to_update,
    )

    # Assert
    # Check grid update
    app.grid_panel.grid.SetCellValue.assert_called_once_with(
        row_to_update, app.docset_status_col_grid_idx, ERROR_BTN_LABEL
    )
    app.grid_panel.grid.ForceRefresh.assert_called_once()

    # Check data source update
    assert (
        app.current_grid_source_data[row_to_update]["docset_status"] == ERROR_BTN_LABEL
    )
    assert "docset_path" not in app.current_grid_source_data[row_to_update]

    # Check logging and user feedback
    app.log_text_ctrl.AppendText.assert_called_once()
    assert "ERROR" in app.log_text_ctrl.AppendText.call_args[0][0]
    wx.MessageBox.assert_called_once()
    assert "Error during generation" in wx.MessageBox.call_args[0][0]
