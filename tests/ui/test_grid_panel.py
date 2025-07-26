"""Tests for the DocsetGridPanel UI component logic."""

from typing import Callable

import pytest
import wx
import wx.grid
from pytest_mock import MockerFixture

from devildex.constants import COLUMNS_ORDER
from devildex.ui.grid_panel import DocsetGridPanel


@pytest.fixture(scope="module")
def wx_app() -> wx.App:
    """Fixture to create a wx.App instance, required for creating wx.Panel."""
    app = wx.App(False)
    return app


@pytest.fixture
def mock_callback(mocker: MockerFixture) -> Callable[[int], None]:
    """Provide a mock callback function for row selection."""
    return mocker.MagicMock(name="on_cell_selected_callback")


@pytest.fixture
def grid_panel(
    wx_app: wx.App, mock_callback: Callable[[int], None], mocker: MockerFixture
) -> DocsetGridPanel:
    """Provide an instance of DocsetGridPanel for testing."""
    # A dummy frame is needed as a parent for the panel
    frame = wx.Frame(None)
    panel = DocsetGridPanel(frame, mock_callback)

    # We can mock the grid methods to avoid real UI operations
    if panel.grid:
        mocker.patch.object(panel.grid, "AppendRows")
        mocker.patch.object(panel.grid, "DeleteRows")
        mocker.patch.object(panel.grid, "SetCellValue")
        mocker.patch.object(panel.grid, "ForceRefresh")
        mocker.patch.object(panel.grid, "SetRowAttr")
        mocker.patch.object(panel.grid, "GetNumberRows", return_value=0)

    frame.Destroy()
    return panel


# --- Test Cases ---


def test_update_data_populates_grid(
    grid_panel: DocsetGridPanel, mocker: MockerFixture
) -> None:
    """Verify that update_data correctly populates the grid with new data."""
    # Arrange
    # Provide data for all columns to make the test robust
    sample_data = [
        {
            "id": "1",
            "name": "pkg-a",
            "version": "1.0",
            "description": "Desc A",
            "status": "OK",
            "docset_status": "Available",
        },
        {
            "id": "2",
            "name": "pkg-b",
            "version": "2.0",
            "description": "Desc B",
            "status": "Error",
            "docset_status": "Not Available",
        },
    ]
    grid = grid_panel.grid
    grid.GetNumberRows.return_value = 0  # Start with an empty grid

    # Act
    grid_panel.update_data(sample_data)

    # Assert
    # Check that rows were added
    grid.AppendRows.assert_called_once_with(2)

    # Check that all cells were populated correctly, using mocker.call
    expected_calls = []
    for r_idx, row_data in enumerate(sample_data):
        for c_idx, col_name in enumerate(COLUMNS_ORDER):
            # The grid column is c_idx + 1 because of the indicator column
            expected_calls.append(
                mocker.call(r_idx, c_idx + 1, str(row_data.get(col_name, "")))
            )

    grid.SetCellValue.assert_has_calls(expected_calls, any_order=True)
    grid.ForceRefresh.assert_called_once()


def test_on_grid_cell_click_handles_selection(
    grid_panel: DocsetGridPanel,
    mock_callback: Callable[[int], None],
    mocker: MockerFixture,  # FIX: Add missing mocker fixture
) -> None:
    """Verify that clicking a cell highlights the row and triggers the callback."""
    # Arrange
    grid = grid_panel.grid
    grid.GetNumberRows.return_value = 5  # Simulate a grid with 5 rows
    mock_event = mocker.MagicMock(spec=wx.grid.GridEvent)
    mock_event.GetRow.return_value = 2  # Simulate clicking on the 3rd row (index 2)

    # Act
    grid_panel._on_grid_cell_click(mock_event)

    # Assert
    # 1. Check that the selection indicator is set
    # Use assert_any_call because other cells might be cleared in the same process
    grid.SetCellValue.assert_any_call(2, grid_panel.indicator_col_idx, "►")

    # 2. Check that the row attribute for highlighting is set
    grid.SetRowAttr.assert_called_once()
    assert grid.SetRowAttr.call_args[0][0] == 2  # Called on the correct row

    # 3. Check that the parent callback was notified with the correct row index
    mock_callback.assert_called_once_with(2)

    # 4. Check that the grid was refreshed
    grid.ForceRefresh.assert_called_once()
    mock_event.Skip.assert_called_once()
