
import wx
import wx.html2


class DevilDexCore():
    def __init__(self):
        pass



class DevilDexApp(wx.App):
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
        super(DevilDexApp, self).__init__(redirect=False)
        self.MainLoop()


    def show_document(self, event=None):
        self.main_panel_sizer.Clear(True)
        self.webview = None
        self.back_button = None
        self.forward_button = None
        self.home_button = None
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
        window_title = "DevilDex"
        self.main_frame = wx.Frame(parent=None, title=window_title, size=(1280, 900))
        self.panel = wx.Panel(self.main_frame)
        self.main_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.main_panel_sizer)
        self.main_frame.Centre()
        self.SetTopWindow(self.main_frame)
        self.view_doc_btn = wx.Button(self.panel, label="Avvia Browser")
        self.main_panel_sizer.AddStretchSpacer(1)
        self.main_panel_sizer.Add(
            self.view_doc_btn, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 20
        )
        self.main_panel_sizer.AddStretchSpacer(1)
        self.view_doc_btn.Bind(
            wx.EVT_BUTTON, self.show_document
        )
        self.main_frame.Show(True)
        return True

    def go_home(self, event=None):
        self.main_panel_sizer.Clear(True)
        self.webview = None
        self.back_button = None
        self.forward_button = None
        self.home_button = None
        self.view_doc_btn = wx.Button(self.panel, label="Avvia Browser")
        self.main_panel_sizer.AddStretchSpacer(1)
        self.main_panel_sizer.Add(
            self.view_doc_btn, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 20
        )
        self.main_panel_sizer.AddStretchSpacer(1)
        self.view_doc_btn.Bind(wx.EVT_BUTTON, self.show_document)
        self.panel.Layout()



    def _setup_navigation_panel(self, panel):
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

    def on_webview_navigated(self, event):
        self.update_navigation_buttons_state()
        event.Skip()

    def update_navigation_buttons_state(self):
        if self.webview and self.back_button and self.forward_button:
            self.back_button.Enable(self.webview.CanGoBack())
            self.forward_button.Enable(self.webview.CanGoForward())

    def on_back(self, event):
        if self.webview.CanGoBack():
            self.webview.GoBack()

    def on_forward(self, event):
        if self.webview.CanGoForward():
            self.webview.GoForward()

    def load_url(self, url_to_load: str):
        if self.webview:
            self.webview.LoadURL(url_to_load)

    def display_page(self, url: str):
        self.load_url(url)
        if self.main_frame and not self.main_frame.IsShown():
            self.main_frame.Show(True)


def main():
    core = DevilDexCore()
    DevilDexApp(core=core, initial_url='https://www.gazzetta.it')

if __name__ == "__main__":
    main()