"""A wx.Panel that encapsulates the main data grid and its logic."""

from typing import Any, Callable

import wx  # type: ignore
import wx.grid  # type: ignore

from devildex.constants import COL_WIDTHS, COLUMNS_ORDER


class DocsetGridPanel(wx.Panel):
    """A panel that encapsulates the main data grid and its related logic."""

    def __init__(
        self, parent: wx.Window, on_cell_selected_callback: Callable[[int], None]
    ) -> None:
        """Initialize the DocsetGridPanel.

        Args:
            parent: The parent window.
            on_cell_selected_callback: A function to call when a row is selected,
                                       passing the row index.

        """
        super().__init__(parent)

        self.on_cell_selected_callback = on_cell_selected_callback
        self.grid: wx.grid.Grid | None = None
        self.custom_highlighted_row_index: int | None = None
        self.custom_row_highlight_attr = wx.grid.GridCellAttr()
        self.custom_row_highlight_attr.SetBackgroundColour(wx.Colour(255, 165, 0))
        self.custom_row_highlight_attr.SetTextColour(wx.BLACK)
        self.indicator_col_idx = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create and arrange the widgets in the panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid = wx.grid.Grid(self)
        self.grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self._on_grid_cell_click)

        num_data_cols = len(COLUMNS_ORDER)
        total_grid_cols = num_data_cols + 1
        self.grid.CreateGrid(0, total_grid_cols)
        self.grid.SetSelectionMode(wx.grid.Grid.SelectRows)
        self._configure_grid_columns()

        sizer.Add(self.grid, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def _configure_grid_columns(self) -> None:
        """Configure the labels, sizes, and attributes of the grid columns."""
        if not self.grid:
            return

        self.grid.SetColLabelValue(self.indicator_col_idx, "")
        self.grid.SetColSize(self.indicator_col_idx, 30)
        indicator_attr = wx.grid.GridCellAttr()
        indicator_attr.SetAlignment(wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
        indicator_attr.SetReadOnly(True)
        self.grid.SetColAttr(self.indicator_col_idx, indicator_attr.Clone())

        for c_idx, col_name in enumerate(COLUMNS_ORDER):
            grid_col_idx = c_idx + 1
            self.grid.SetColLabelValue(grid_col_idx, col_name)
            if col_name in COL_WIDTHS:
                self.grid.SetColSize(grid_col_idx, COL_WIDTHS[col_name])
            col_attr = wx.grid.GridCellAttr()
            col_attr.SetReadOnly(True)
            self.grid.SetColAttr(grid_col_idx, col_attr.Clone())

    def update_data(self, table_data: list[dict[str, Any]]) -> None:
        """Populate the grid with new data."""
        if not self.grid:
            return

        self.custom_highlighted_row_index = None

        num_rows = len(table_data)
        current_grid_rows = self.grid.GetNumberRows()
        if current_grid_rows < num_rows:
            self.grid.AppendRows(num_rows - current_grid_rows)
        elif current_grid_rows > num_rows:
            self.grid.DeleteRows(num_rows, current_grid_rows - num_rows)

        for r_idx, row_dict in enumerate(table_data):
            for c_idx, col_name in enumerate(COLUMNS_ORDER):
                cell_value = row_dict.get(col_name, "")
                self.grid.SetCellValue(r_idx, c_idx + 1, str(cell_value))
        self.grid.ForceRefresh()

    def _on_grid_cell_click(self, event: wx.grid.GridEvent) -> None:
        """Handle click on a grid cell, update UI, and notify the parent."""
        if not self.grid:
            event.Skip()
            return

        clicked_row = event.GetRow()

        if self.custom_highlighted_row_index is not None:
            self.grid.SetRowAttr(
                self.custom_highlighted_row_index, wx.grid.GridCellAttr()
            )
            if self.grid.GetNumberRows() > self.custom_highlighted_row_index:
                self.grid.SetCellValue(
                    self.custom_highlighted_row_index, self.indicator_col_idx, ""
                )

        if 0 <= clicked_row < self.grid.GetNumberRows():
            self.grid.SetCellValue(clicked_row, self.indicator_col_idx, "►")
            self.custom_row_highlight_attr.IncRef()
            self.grid.SetRowAttr(clicked_row, self.custom_row_highlight_attr)
            self.custom_highlighted_row_index = clicked_row
            self.on_cell_selected_callback(clicked_row)

        self.grid.ForceRefresh()
        event.Skip()
