
import wx
import wx.dataview as dv
import wx.html2

from examples.sample_data import PACKAGES_DATA


class PackageTreeModel(dv.PyDataViewModel):
    def __init__(self, data):
        super().__init__()
        self.data = [1, 2, 3]
        self.objMap = {}
        self.next_id = 1

    def GetColumnCount(self):
        """Restituisce il numero di colonne."""
        return 1  # Solo una colonna

    def GetColumnType(self, col):
        """Indica il tipo di dati per la colonna."""
        # La prima colonna (e unica in questo caso) di un DataViewTreeCtrl
        # si aspetta "wxDataViewIconText"
        if col == 0:
            return "wxDataViewIconText"
        return "string"  # Non dovrebbe essere raggiunto con 1 colonna

    def GetChildren(self, parent_item, children_list):
        """Popola 'children_list' con gli item figli di 'parent_item'."""
        # Se parent_item è None, stiamo chiedendo gli elementi radice
        if not parent_item:
            for item_data in self.data:
                current_id = self.next_id
                item_id = id(item_data)
                self.objMap[current_id] = item_data
                children_list.append(dv.DataViewItem(item_id))
                self.next_id += 1
            return len(self.data)
        return 0

    def IsContainer(self, item):
        """Restituisce True se l'item può avere figli."""
        # Se item è None, si riferisce alla radice invisibile, che è un container
        if not item:
            return True
        # I nostri numeri (1, 2, 3) non sono container in questo modello semplice
        return False

    def GetParent(self, item):
        """Restituisce il genitore dell'item."""
        # Se item è None, o se l'item non ha un genitore (è un item radice),
        # restituisci un DataViewItem invalido.
        if not item:
            return dv.DataViewItem(0)  # Item invalido

        # I nostri numeri (1, 2, 3) sono elementi radice, quindi non hanno genitore
        return dv.DataViewItem(0)  # Item invalido

    def GetValue(self, item, col):
        """Restituisce il valore da visualizzare per l'item e la colonna specificati."""
        # Recupera il dato reale associato all'ID dell'item
        print(self.objMap)
        item_data = self.objMap.get(item.GetID())
        if item_data is None:
            if col == 0:
                return dv.DataViewIconText("")  # Valore di fallback
            return ""

        # Abbiamo solo la colonna 0
        if col == 0:
            # La colonna 0 si aspetta un oggetto DataViewIconText.
            # Convertiamo il nostro numero in stringa per visualizzarlo.
            return dv.DataViewIconText(str(item_data))

        return ""  # Non dovrebbe essere raggiunto

        # Opzionale, ma buona pratica includerlo

    def HasDefaultCompare(self):
        return True
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

        self.view_doc_btn = None
        self.package_table: dv.DataViewTreeCtrl | None = None
        self.package_model: PackageTreeModel | None = None

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

        self.main_panel_sizer.AddStretchSpacer(1)
        self.main_panel_sizer.Add(
            self.view_doc_btn, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP | wx.BOTTOM, 10
        )

        self.main_panel_sizer.AddStretchSpacer(1)
        self.view_doc_btn.Bind(
            wx.EVT_BUTTON, self.show_document
        )
        self.package_table = dv.DataViewTreeCtrl(
            self.panel, style=dv.DV_ROW_LINES | dv.DV_VERT_RULES | dv.DV_MULTIPLE
        )
        self.package_table.AppendTextColumn(
            "Pacchetto", 0, width=250, mode=dv.DATAVIEW_CELL_ACTIVATABLE
        )
        self.package_table.AppendTextColumn(
            "Descrizione", 1, width=350, mode=dv.DATAVIEW_CELL_ACTIVATABLE
        )
        self.package_table.AppendTextColumn(
            "Stato", 2, width=150, mode=dv.DATAVIEW_CELL_ACTIVATABLE
        )
        self.package_table.AppendTextColumn(
            "Versione/Data", 3, width=200, mode=dv.DATAVIEW_CELL_ACTIVATABLE
        )

        self.package_model = PackageTreeModel(PACKAGES_DATA)
        self.package_table.AssociateModel(self.package_model)
        self.main_panel_sizer.Add(
            self.package_table, 1, wx.EXPAND | wx.ALL, 5
        )

        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()

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
        self.package_table = None

        self.webview = None
        self.back_button = None
        self.forward_button = None
        self.home_button = None

        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()


def main():
    core = DevilDexCore()
    DevilDexApp(core=core, initial_url='https://www.gazzetta.it')

if __name__ == "__main__":
    main()