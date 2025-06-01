"""main application."""
from typing import Dict, List, Optional

import wx.grid
import wx.html2

from examples.sample_data import COLUMNS_ORDER, PACKAGES_DATA


class DevilDexCore:
    """DevilDex Core."""

    def __init__(self) -> None:
        """Initialize a new DevilDexCore instance."""
        pass

class DevilDexApp(wx.App):
    """Main Application."""

    def __init__(self, core: DevilDexCore| None = None, initial_url: str| None = None) -> None:
        """Initialize a new DevilDexApp instance."""
        self.core = core
        self.home_url = "https://www.google.com"
        self.initial_url = initial_url
        self.main_frame: Optional[wx.Frame] = None
        self.webview: Optional[wx.html2.WebView] = None
        self.back_button: Optional[wx.Button] = None
        self.forward_button: Optional[wx.Button] = None
        self.home_button: Optional[wx.Button] = None
        self.panel: Optional[wx.Panel] = None
        self.main_panel_sizer: Optional[wx.BoxSizer] = None
        self.data_grid: wx.grid.Grid | None = None
        self.view_doc_btn: Optional[wx.Button] = None
        self.current_grid_source_data: list[dict] = []
        self.open_action_button: wx.Button | None = None
        self.generate_action_button: wx.Button | None = None
        self.regenerate_action_button: wx.Button | None = None
        self.view_log_action_button: wx.Button | None = None
        self.delete_action_button: wx.Button | None = None
        self.selected_row_index: int | None = None
        self.custom_highlighted_row_index: Optional[int] = None
        self.custom_row_highlight_attr: Optional[wx.grid.GridCellAttr] = None
        self.indicator_col_idx = 0
        super().__init__(redirect=False)
        self.MainLoop()


    def show_document(self, event: wx.CommandEvent| None = None) -> None:
        """Show the document view."""
        if event:
            event.Skip()
        self._clear_main_panel()
        button_sizer = self._setup_navigation_panel(self.panel)
        self.main_panel_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)
        self.webview = wx.html2.WebView.New(self.panel)
        self.main_panel_sizer.Add(self.webview, 1, wx.EXPAND | wx.ALL, 5)
        self.update_navigation_buttons_state()
        self.webview.Bind(wx.html2.EVT_WEBVIEW_NAVIGATED, self.on_webview_navigated)
        if self.initial_url:
            self.load_url(self.initial_url)
        self.panel.Layout()

    def OnInit(self) -> bool:  # noqa: N802
        """Set up gui widgets on application startup."""
        wx.Log.SetActiveTarget(wx.LogStderr())
        window_title = "DevilDex"
        self.main_frame = wx.Frame(parent=None, title=window_title, size=(1280, 900))
        self.panel = wx.Panel(self.main_frame)
        self.main_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.main_panel_sizer)
        self.main_frame.Centre()
        self.SetTopWindow(self.main_frame)
        self.custom_row_highlight_attr = wx.grid.GridCellAttr()
        self.custom_row_highlight_attr.SetBackgroundColour(
            wx.Colour(255, 165, 0)
        )
        self.custom_row_highlight_attr.SetTextColour(
            wx.BLACK
        )

        self._setup_initial_view()
        self.main_frame.Show(True)
        return True

    def go_home(self, event: wx.CommandEvent| None =None) -> None:
        """Go to initial view."""
        if event:
            event.Skip()
        self._setup_initial_view()

    def _setup_initial_view(self) -> None:
        """Configura la initial window (per ora solo il button)."""
        self._clear_main_panel()
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.view_doc_btn = wx.Button(self.panel, label="Start Browser")
        self.main_panel_sizer.Add(
            self.view_doc_btn, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP | wx.BOTTOM, 10
        )
        self.view_doc_btn.Bind(
            wx.EVT_BUTTON, self.show_document
        )
        self.data_grid = wx.grid.Grid(self.panel)
        content_sizer.Add(
            self.data_grid, 1, wx.EXPAND | wx.ALL, 5
        )
        self.data_grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.on_grid_cell_click)
        self.update_grid()
        action_buttons_sizer = self._setup_action_buttons_panel(self.panel)
        content_sizer.Add(
            action_buttons_sizer, 0, wx.EXPAND | wx.ALL, 5
        )
        self.main_panel_sizer.Add(
            content_sizer, 1, wx.EXPAND | wx.ALL, 0
        )

        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()

    def on_open_docset(self, event: wx.CommandEvent) -> None:
        """Handle open docset action."""
        print(f"Action: Apri Docset per riga {self.selected_row_index}")
        sel_data = self.get_selected_row()
        if sel_data:
            print(sel_data)
        event.Skip()

    def on_generate_docset(self, event: wx.CommandEvent) -> None:
        """Handle generate docset action."""
        print(f"Action: Genera Docset per riga {self.selected_row_index}")
        sel_data = self.get_selected_row()
        if sel_data:
            print(sel_data)
        event.Skip()

    def on_regenerate_docset(self, event: wx.CommandEvent) -> None:
        """Handle regenerate docset action."""
        print(f"Action: Regenerate Docset per riga {self.selected_row_index}")
        sel_data = self.get_selected_row()
        if sel_data:
            print(sel_data)
        event.Skip()

    def on_view_log(self, event: wx.CommandEvent) -> None:
        """Handle view log action."""
        print(f"Action: View Log for row {self.selected_row_index}")
        sel_data = self.get_selected_row()
        if sel_data:
            print(sel_data)
        event.Skip()

    def on_delete_docset(self, event: wx.CommandEvent) -> None:
        """Handle delete docset action."""
        print(f"Action: Delete Docset per riga {self.selected_row_index}")
        sel_data = self.get_selected_row()
        if sel_data:
            print(sel_data)
        event.Skip()

    def on_grid_cell_click(self, event: wx.grid.GridEvent) -> None:
        """Handle click on a grid cell."""
        if not self.data_grid or not self.custom_row_highlight_attr:
            print(
                "ERROR: data_grid o custom_row_highlight_attr not initialized in on_grid_cell_click."
            )
            if event:
                event.Skip()
            return
        clicked_row = event.GetRow()
        clicked_column = event.GetCol()
        if (
            self.custom_highlighted_row_index is not None
            and self.custom_highlighted_row_index != clicked_row
        ):
            self.data_grid.SetRowAttr(self.custom_highlighted_row_index, None)
            if self.data_grid.GetNumberRows() > self.custom_highlighted_row_index:
                self.data_grid.SetCellValue(self.custom_highlighted_row_index, self.indicator_col_idx, "")

        if self.data_grid.GetNumberRows() > clicked_row >= 0:

            self.data_grid.SetCellValue(clicked_row, self.indicator_col_idx, "►")


            self.custom_row_highlight_attr.IncRef()
            self.data_grid.SetRowAttr(clicked_row, self.custom_row_highlight_attr)

            self.custom_highlighted_row_index = clicked_row
            self.selected_row_index = clicked_row
        else:
            print(
                f"Warning: clicked row {clicked_row} non valida, not applying arrow/color."
            )

        self.data_grid.ForceRefresh()

        print("--- Click sulla cell ---")
        print(f"Row (index): {clicked_row}")
        print(f"Column (index): {clicked_column}")
        cell_content = self.data_grid.GetCellValue(
            clicked_row, clicked_column
        )
        print(f"Content clicked cell: '{cell_content}'")

        grid_row_data = []
        if self.data_grid:
            num_columns = self.data_grid.GetNumberCols()
            for col_idx in range(num_columns):
                grid_row_data.append(
                    self.data_grid.GetCellValue(clicked_row, col_idx)
                )
            print(f"Row Data (from grid): {grid_row_data}")

        if 0 <= clicked_row < len(self.current_grid_source_data):
            original_row_dictionary = self.current_grid_source_data[clicked_row]
            print(f"Dati riga (original dictionary): {original_row_dictionary}")

            if "package_name" in original_row_dictionary:
                print(
                    f"Value di 'package_name' dal dictionary: {original_row_dictionary['nome_pacchetto']}"
                )
        else:
            print("Error: riga index non valido per current_grid_source_data.")

        print("--------------------------")

        self._update_action_buttons_state()
        event.Skip()

    def _setup_navigation_panel(self, panel: wx.Panel) -> wx.Sizer:
        icon_size = wx.DefaultSize
        back_icon = wx.ArtProvider.GetBitmap(wx.ART_GO_BACK, wx.ART_BUTTON, icon_size)
        forward_icon = wx.ArtProvider.GetBitmap(
            wx.ART_GO_FORWARD, wx.ART_BUTTON, icon_size
        )
        home_icon = wx.ArtProvider.GetBitmap(wx.ART_GO_HOME, wx.ART_BUTTON, icon_size)
        self.back_button = wx.Button(panel)
        self.forward_button = wx.Button(panel)
        self.home_button = wx.Button(panel)
        if back_icon.IsOk():
            self.back_button.SetBitmap(back_icon, wx.LEFT)
        if forward_icon.IsOk():
            self.forward_button.SetBitmap(forward_icon, wx.LEFT)
        if home_icon.IsOk():
            self.home_button.SetBitmap(home_icon, wx.LEFT)
        self.back_button.Bind(wx.EVT_BUTTON, self.on_back)
        self.forward_button.Bind(wx.EVT_BUTTON, self.on_forward)
        self.home_button.Bind(wx.EVT_BUTTON, self.go_home)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.back_button, 0, wx.ALL, 5)
        button_sizer.Add(self.forward_button, 0, wx.ALL, 5)
        button_sizer.Add(self.home_button, 0, wx.ALL, 5)
        return button_sizer

    def on_webview_navigated(self, event: wx.html2.WebViewEvent) -> None:
        """Handle page change event to update their state."""
        self.update_navigation_buttons_state()
        event.Skip()

    def update_navigation_buttons_state(self) -> None:
        """Update navigation buttons state."""
        if self.webview and self.back_button and self.forward_button:
            self.back_button.Enable(self.webview.CanGoBack())
            self.forward_button.Enable(self.webview.CanGoForward())

    def on_back(self, event: wx.CommandEvent) -> None:
        """Handle browser back button click."""
        if event:
            event.Skip()
        if self.webview.CanGoBack():
            self.webview.GoBack()

    def get_selected_row(self) -> dict | None:
        """Get selected row data."""
        if self.selected_row_index is not None and 0 <= self.selected_row_index < len(
            self.current_grid_source_data
        ):
            return self.current_grid_source_data[self.selected_row_index]
        return None


    def update_grid(self, data: Optional[List[Dict]] = None) -> None:
        """Populate self.data_grid con i dati."""
        self.selected_row_index = None
        self.custom_highlighted_row_index = None
        self._update_action_buttons_state()
        table_data = data
        if table_data is None:
            table_data = PACKAGES_DATA
        self.current_grid_source_data = table_data

        num_rows = len(table_data)
        num_cols = len(COLUMNS_ORDER) + 1

        self.data_grid.CreateGrid(num_rows, num_cols)
        self.data_grid.SetSelectionMode(
            wx.grid.Grid.SelectRows
        )
        self.data_grid.SetColLabelValue(
            self.indicator_col_idx, ""
        )
        self.data_grid.SetColSize(self.indicator_col_idx, 30)
        indicator_attr = wx.grid.GridCellAttr()
        indicator_attr.SetAlignment(
            wx.ALIGN_CENTRE, wx.ALIGN_CENTRE
        )
        indicator_attr.SetReadOnly(True)
        self.data_grid.SetColAttr(self.indicator_col_idx, indicator_attr)
        for c_idx, col_name in enumerate(COLUMNS_ORDER):
            self.data_grid.SetColLabelValue(c_idx + 1, col_name)

        for r_idx, row_dict in enumerate(table_data):
            for c_idx, col_name in enumerate(COLUMNS_ORDER):
                cell_value = row_dict.get(col_name, "")
                self.data_grid.SetCellValue(r_idx, c_idx + 1, str(cell_value))

        self.data_grid.AutoSizeColumns()
        self.data_grid.ForceRefresh()



    def on_forward(self, event: wx.CommandEvent) -> None:
        """Handle browser forward button click."""
        if event:
            event.Skip()
        if self.webview.CanGoForward():
            self.webview.GoForward()

    def load_url(self, url_to_load: str) -> None:
        """Load in webview given url."""
        if self.webview:
            self.webview.LoadURL(url_to_load)


    def _clear_main_panel(self) -> None:
        """Clear il main_panel_sizer e empties references to widget."""
        if self.main_panel_sizer and self.main_panel_sizer.GetItemCount() > 0:
            self.main_panel_sizer.Clear(True)
        self.view_doc_btn = None
        self.webview = None
        self.back_button = None
        self.forward_button = None
        self.home_button = None
        self.data_grid = None
        self.selected_row_index = None
        self.custom_highlighted_row_index = None
        self.open_action_button = None
        self.generate_action_button = None
        self.regenerate_action_button = None
        self.view_log_action_button = None
        self.delete_action_button = None
        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()

    def _update_action_buttons_state(self) -> None:
        """Update state (enabled/disabled) of action buttons."""
        buttons_are_conditionally_enabled = self.selected_row_index is not None
        action_buttons_references = [
            self.open_action_button,
            self.generate_action_button,
            self.regenerate_action_button,
            self.view_log_action_button,
            self.delete_action_button,
        ]
        if not buttons_are_conditionally_enabled:
            print("No row selected, disabling action buttons.")
        else:
            print(
                f"selected row: {self.selected_row_index}. Enable tutti i action buttons (temporarily)."
            )
        for button in action_buttons_references:
            if button:
                button.Enable(buttons_are_conditionally_enabled)

    def _setup_action_buttons_panel(self, parent: wx.Window) -> wx.Sizer:
        action_box = wx.StaticBox(parent, label="Docset Actions")
        static_box_sizer = wx.StaticBoxSizer(action_box, wx.VERTICAL)
        buttons_internal_sizer = wx.BoxSizer(wx.VERTICAL)

        button_definitions = [
            ("Open Docset 📖", "open_action_button", self.on_open_docset),
            ("Generate Docset 🛠️", "generate_action_button", self.on_generate_docset),
            (
                "Regenerate Docset 🔄",
                "regenerate_action_button",
                self.on_regenerate_docset,
            ),
            ("View Error Log ❗", "view_log_action_button", self.on_view_log),
            ("Delete Docset 🗑️", "delete_action_button", self.on_delete_docset),
        ]

        for label, attr_name, handler in button_definitions:
            button = wx.Button(action_box, label=label)
            setattr(self, attr_name, button)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons_internal_sizer.Add(
                button, 0, wx.EXPAND | wx.ALL, 5
            )
            button.Enable(False)
        static_box_sizer.Add(buttons_internal_sizer, 1, wx.EXPAND | wx.ALL, 5)
        return static_box_sizer

def main() -> None:
    """Launch whole application."""
    core = DevilDexCore()
    DevilDexApp(core=core, initial_url='https://www.gazzetta.it')

if __name__ == "__main__":
    main()