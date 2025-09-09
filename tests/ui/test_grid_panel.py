"""Tests for the DocsetGridPanel UI component logic."""

from typing import Callable

import pytest
import wx
import wx.grid
from pytest_mock import MockerFixture

from devildex.constants import COLUMNS_ORDER
from devildex.ui.grid_panel import DocsetGridPanel

TEST_ROW_INDEX = 2


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
    frame = wx.Frame(None)
    panel = DocsetGridPanel(frame, mock_callback)

    if panel.grid:
        mocker.patch.object(panel.grid, "AppendRows")
        mocker.patch.object(panel.grid, "DeleteRows")
        mocker.patch.object(panel.grid, "SetCellValue")
        mocker.patch.object(panel.grid, "ForceRefresh")
        mocker.patch.object(panel.grid, "SetRowAttr")
        mocker.patch.object(panel.grid, "GetNumberRows", return_value=0)

    frame.Destroy()
    return panel


@pytest.mark.ui
def test_update_data_populates_grid(
    grid_panel: DocsetGridPanel, mocker: MockerFixture
) -> None:
    """Verify that update_data correctly populates the grid with new data."""
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
    grid.GetNumberRows.return_value = 0

    grid_panel.update_data(sample_data)

    grid.AppendRows.assert_called_once_with(2)

    expected_calls = []
    for r_idx, row_data in enumerate(sample_data):
        for c_idx, col_name in enumerate(COLUMNS_ORDER):
            expected_calls.append(
                mocker.call(r_idx, c_idx + 1, str(row_data.get(col_name, "")))
            )

    grid.SetCellValue.assert_has_calls(expected_calls, any_order=True)
    grid.ForceRefresh.assert_called_once()


@pytest.mark.ui
def test_on_grid_cell_click_handles_selection(
    grid_panel: DocsetGridPanel,
    mock_callback: Callable[[int], None],
    mocker: MockerFixture,
) -> None:
    """Verify that clicking a cell highlights the row and triggers the callback."""
    grid = grid_panel.grid
    grid.GetNumberRows.return_value = 5
    mock_event = mocker.MagicMock(spec=wx.grid.GridEvent)
    mock_event.GetRow.return_value = 2

    grid_panel._on_grid_cell_click(mock_event)

    grid.SetCellValue.assert_any_call(2, grid_panel.indicator_col_idx, "►")

    grid.SetRowAttr.assert_called_once()
    assert grid.SetRowAttr.call_args[0][0] == TEST_ROW_INDEX

    mock_callback.assert_called_once_with(2)

    grid.ForceRefresh.assert_called_once()
    mock_event.Skip.assert_called_once()
