"""A wx.Panel that encapsulates the document web view and its navigation controls."""

import logging
from typing import Callable

import wx
import wx.html2

logger = logging.getLogger(__name__)


class DocumentViewPanel(wx.Panel):
    """A panel that displays a docset using a WebView and provides navigation."""

    def __init__(self, parent: wx.Window, on_home_callback: Callable[[], None]) -> None:
        """Initialize the DocumentViewPanel.

        Args:
            parent: The parent window.
            on_home_callback: A function to call when the 'Home' button is clicked.

        """
        super().__init__(parent)
        self.on_home_callback = on_home_callback

        self.webview: wx.html2.WebView | None = None
        self.back_button: wx.Button | None = None
        self.forward_button: wx.Button | None = None
        self.home_button: wx.Button | None = None
        self.package_display_label: wx.StaticText | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create and arrange the widgets in the panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.package_display_label = wx.StaticText(self, label="Loading document...")
        font = self.package_display_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.package_display_label.SetFont(font)
        sizer.Add(
            self.package_display_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5
        )

        nav_sizer = self._setup_navigation_panel(self)
        sizer.Add(nav_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)

        self.webview = wx.html2.WebView.New(self)
        self.webview.Bind(wx.html2.EVT_WEBVIEW_NAVIGATING, self._on_webview_event)
        self.webview.Bind(wx.html2.EVT_WEBVIEW_NAVIGATED, self._on_webview_event)
        self.webview.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._on_webview_event)
        self.webview.Bind(wx.html2.EVT_WEBVIEW_ERROR, self._on_webview_event)
        self.webview.Bind(wx.html2.EVT_WEBVIEW_NEWWINDOW, self._on_webview_event)
        self.webview.Bind(
            wx.html2.EVT_WEBVIEW_FULLSCREEN_CHANGED, self._on_webview_event
        )
        self.webview.Bind(
            wx.html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_webview_event
        )
        self.webview.Bind(wx.html2.EVT_WEBVIEW_TITLE_CHANGED, self._on_webview_event)

        sizer.Add(self.webview, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)
        self.update_navigation_buttons_state()

    def _setup_navigation_panel(self, parent: wx.Panel) -> wx.Sizer:
        """Create the Back, Forward, and Home navigation buttons."""
        icon_size = wx.DefaultSize
        back_icon = wx.ArtProvider.GetBitmap(wx.ART_GO_BACK, wx.ART_BUTTON, icon_size)
        forward_icon = wx.ArtProvider.GetBitmap(
            wx.ART_GO_FORWARD, wx.ART_BUTTON, icon_size
        )
        home_icon = wx.ArtProvider.GetBitmap(wx.ART_GO_HOME, wx.ART_BUTTON, icon_size)

        self.back_button = wx.Button(parent)
        self.forward_button = wx.Button(parent)
        self.home_button = wx.Button(parent)

        if back_icon.IsOk():
            self.back_button.SetBitmap(wx.BitmapBundle(back_icon), wx.LEFT)
        if forward_icon.IsOk():
            self.forward_button.SetBitmap(wx.BitmapBundle(forward_icon), wx.LEFT)
        if home_icon.IsOk():
            self.home_button.SetBitmap(wx.BitmapBundle(home_icon), wx.LEFT)

        self.back_button.Bind(wx.EVT_BUTTON, self._on_back)
        self.forward_button.Bind(wx.EVT_BUTTON, self._on_forward)
        self.home_button.Bind(wx.EVT_BUTTON, lambda evt: self.on_home_callback())

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.back_button, 0, wx.ALL, 5)
        button_sizer.Add(self.forward_button, 0, wx.ALL, 5)
        button_sizer.Add(self.home_button, 0, wx.ALL, 5)
        return button_sizer

    @staticmethod
    def _on_webview_event(event: wx.html2.WebViewEvent) -> None:
        event.Skip()

    def load_url(self, url_to_load: str) -> None:
        """Load a specific URL into the WebView."""
        if self.webview:
            self.webview.LoadURL(url_to_load)

    def set_document_title(self, title: str) -> None:
        """Update the title label displayed above the WebView."""
        if self.package_display_label:
            self.package_display_label.SetLabel(title)

    def _on_webview_navigated(self, event: wx.html2.WebViewEvent) -> None:
        """Update navigation button states when the page changes."""
        self.update_navigation_buttons_state()
        event.Skip()

    def update_navigation_buttons_state(self) -> None:
        """Enable or disable back/forward buttons based on WebView state."""
        if self.webview and self.back_button and self.forward_button:
            self.back_button.Enable(self.webview.CanGoBack())
            self.forward_button.Enable(self.webview.CanGoForward())

    def _on_back(self, event: wx.CommandEvent) -> None:
        """Handle the 'Back' button click."""
        if self.webview and self.webview.CanGoBack():
            self.webview.GoBack()
        event.Skip()

    def _on_forward(self, event: wx.CommandEvent) -> None:
        """Handle the 'Forward' button click."""
        if self.webview and self.webview.CanGoForward():
            self.webview.GoForward()
        event.Skip()
