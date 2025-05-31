import wx.grid
import wx.html2

from examples.sample_data import COLUMNS_ORDER, PACKAGES_DATA


class DevilDexCore():
    def __init__(self):
        pass

class DevilDexApp(wx.App):
    """Main Application."""

    def __init__(self, core: DevilDexCore| None = None, initial_url: str| None = None):
        self.core = core
        self.home_url = "https://www.google.com"
        self.initial_url = initial_url
        self.main_frame = None
        self.webview = None
        self.back_button = None
        self.forward_button = None
        self.home_button = None
        self.panel = None
        self.main_panel_sizer = None
        self.data_grid: wx.grid.Grid | None = None
        self.view_doc_btn = None
        self.current_grid_source_data: list[dict] = []
        super(DevilDexApp, self).__init__(redirect=False)
        self.MainLoop()


    def show_document(self, event: wx.CommandEvent| None = None):
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

    def OnInit(self):
        wx.Log.SetActiveTarget(wx.LogStderr())
        window_title = "DevilDex"
        self.main_frame = wx.Frame(parent=None, title=window_title, size=(1280, 900))
        self.panel = wx.Panel(self.main_frame)
        self.main_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.main_panel_sizer)
        self.main_frame.Centre()
        self.SetTopWindow(self.main_frame)
        self._setup_initial_view()
        self.main_frame.Show(True)
        return True

    def go_home(self, event: wx.CommandEvent| None =None):
        if event:
            event.Skip()
        self._setup_initial_view()

    def _setup_initial_view(self):
        """Configura la schermata iniziale (per ora solo il pulsante)."""
        self._clear_main_panel()
        self.view_doc_btn = wx.Button(self.panel, label="Avvia Browser")
        self.main_panel_sizer.Add(
            self.view_doc_btn, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP | wx.BOTTOM, 10
        )
        self.view_doc_btn.Bind(
            wx.EVT_BUTTON, self.show_document
        )
        self.data_grid = wx.grid.Grid(self.panel)
        self.main_panel_sizer.Add(
            self.data_grid, 1, wx.EXPAND | wx.ALL, 5
        )
        self.data_grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.on_grid_cell_click)
        self.update_grid()
        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()



    def on_grid_cell_click(self, event: wx.grid.GridEvent):
        """Gestisce il click su una cella della griglia."""
        riga_cliccata = event.GetRow()
        colonna_cliccata = event.GetCol()

        print("--- Click sulla cella ---")
        print(f"Riga (indice): {riga_cliccata}")
        print(f"Colonna (indice): {colonna_cliccata}")

        contenuto_cella = self.data_grid.GetCellValue(
            riga_cliccata, colonna_cliccata
        )
        print(f"Contenuto cella cliccata: '{contenuto_cella}'")

        dati_riga_dalla_griglia = []
        if self.data_grid:
            num_colonne_griglia = self.data_grid.GetNumberCols()
            for col_idx in range(num_colonne_griglia):
                dati_riga_dalla_griglia.append(
                    self.data_grid.GetCellValue(riga_cliccata, col_idx)
                )
            print(f"Dati riga (dalla griglia): {dati_riga_dalla_griglia}")

        if 0 <= riga_cliccata < len(self.current_grid_source_data):
            dizionario_riga_originale = self.current_grid_source_data[riga_cliccata]
            print(f"Dati riga (dizionario originale): {dizionario_riga_originale}")

            if "nome_pacchetto" in dizionario_riga_originale:
                print(
                    f"Valore di 'nome_pacchetto' dal dizionario: {dizionario_riga_originale['nome_pacchetto']}"
                )
        else:
            print("Errore: Indice di riga non valido per current_grid_source_data.")

        print("--------------------------")

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

    def on_webview_navigated(self, event: wx.html2.WebViewEvent):
        self.update_navigation_buttons_state()
        event.Skip()

    def update_navigation_buttons_state(self):
        if self.webview and self.back_button and self.forward_button:
            self.back_button.Enable(self.webview.CanGoBack())
            self.forward_button.Enable(self.webview.CanGoForward())

    def on_back(self, event: wx.CommandEvent):
        if event:
            event.Skip()
        if self.webview.CanGoBack():
            self.webview.GoBack()

    def update_grid(self, data=None):
        """Popola self.data_grid con i dati."""
        table_data = data
        if table_data is None:
            table_data = PACKAGES_DATA
        self.current_grid_source_data = table_data

        num_rows = len(table_data)
        num_cols = len(COLUMNS_ORDER)

        self.data_grid.CreateGrid(num_rows, num_cols)

        for c_idx, col_name in enumerate(COLUMNS_ORDER):
            self.data_grid.SetColLabelValue(c_idx, col_name)

        for r_idx, row_dict in enumerate(table_data):
            for c_idx, col_name in enumerate(COLUMNS_ORDER):
                cell_value = row_dict.get(col_name, "")
                self.data_grid.SetCellValue(r_idx, c_idx, str(cell_value))

        self.data_grid.AutoSizeColumns()



    def on_forward(self, event: wx.CommandEvent):
        if event:
            event.Skip()
        if self.webview.CanGoForward():
            self.webview.GoForward()

    def load_url(self, url_to_load: str):
        if self.webview:
            self.webview.LoadURL(url_to_load)


    def _clear_main_panel(self):
        """Pulisce il main_panel_sizer e resetta i riferimenti ai widget."""
        if self.main_panel_sizer and self.main_panel_sizer.GetItemCount() > 0:
            self.main_panel_sizer.Clear(True)
        self.view_doc_btn = None
        self.webview = None
        self.back_button = None
        self.forward_button = None
        self.home_button = None
        self.data_grid = None
        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()


def main():
    core = DevilDexCore()
    DevilDexApp(core=core, initial_url='https://www.gazzetta.it')

if __name__ == "__main__":
    main()