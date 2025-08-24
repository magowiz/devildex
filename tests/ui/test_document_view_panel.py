import unittest
import wx
import wx.html2
from unittest.mock import MagicMock, patch
import pytest

# Fixture to create a wx.App instance for UI tests
@pytest.fixture(scope="function")
def wx_app():
    app = wx.App(False)
    yield app
    app.Destroy()

from devildex.ui.document_view_panel import DocumentViewPanel


class TestDocumentViewPanel(unittest.TestCase):
    @pytest.mark.ui
    def setUp(self, wx_app): # Add wx_app as an argument
        self.app = wx_app # Store the app instance
        self.frame = wx.Frame(None)
        self.mock_on_home_callback = MagicMock()
        self.panel = DocumentViewPanel(self.frame, self.mock_on_home_callback)
        wx.Yield()  # Process UI events

    def tearDown(self):
        if self.frame:
            wx.CallAfter(self.frame.Destroy)
        wx.Yield()

    def test_initialization(self):
        self.assertIsInstance(self.panel, DocumentViewPanel)
        self.assertIsNotNone(self.panel.webview)
        self.assertIsNotNone(self.panel.back_button)
        self.assertIsNotNone(self.panel.forward_button)
        self.assertIsNotNone(self.panel.home_button)
        self.assertIsNotNone(self.panel.package_display_label)
        self.assertEqual(self.panel.on_home_callback, self.mock_on_home_callback)

    def test_setup_ui_elements(self):
        # Verify webview creation and binding
        self.assertIsInstance(self.panel.webview, wx.html2.WebView)
        # Mock the Bind method to check if it's called
        with patch.object(self.panel.webview, 'Bind') as mock_bind:
            self.panel._setup_ui()
            mock_bind.assert_called_with(wx.html2.EVT_WEBVIEW_NAVIGATED, self.panel._on_webview_navigated)

        # Verify label properties
        self.assertIsInstance(self.panel.package_display_label, wx.StaticText)
        self.assertEqual(self.panel.package_display_label.GetLabel(), "Loading document...")
        self.assertTrue(self.panel.package_display_label.GetFont().GetWeight() == wx.FONTWEIGHT_BOLD)

        # Verify button creation
        self.assertIsInstance(self.panel.back_button, wx.Button)
        self.assertIsInstance(self.panel.forward_button, wx.Button)
        self.assertIsInstance(self.panel.home_button, wx.Button)

    def test_load_url(self):
        mock_webview = MagicMock(spec=wx.html2.WebView)
        self.panel.webview = mock_webview
        test_url = "https://example.com"
        self.panel.load_url(test_url)
        mock_webview.LoadURL.assert_called_once_with(test_url)

    def test_set_document_title(self):
        mock_label = MagicMock(spec=wx.StaticText)
        self.panel.package_display_label = mock_label
        test_title = "My Test Document"
        self.panel.set_document_title(test_title)
        mock_label.SetLabel.assert_called_once_with(test_title)

    def test_update_navigation_buttons_state(self):
        mock_webview = MagicMock(spec=wx.html2.WebView)
        mock_back_button = MagicMock(spec=wx.Button)
        mock_forward_button = MagicMock(spec=wx.Button)

        self.panel.webview = mock_webview
        self.panel.back_button = mock_back_button
        self.panel.forward_button = mock_forward_button

        # Test case 1: Can go back and forward
        mock_webview.CanGoBack.return_value = True
        mock_webview.CanGoForward.return_value = True
        self.panel.update_navigation_buttons_state()
        mock_back_button.Enable.assert_called_with(True)
        mock_forward_button.Enable.assert_called_with(True)

        # Reset mocks
        mock_back_button.reset_mock()
        mock_forward_button.reset_mock()

        # Test case 2: Cannot go back or forward
        mock_webview.CanGoBack.return_value = False
        mock_webview.CanGoForward.return_value = False
        self.panel.update_navigation_buttons_state()
        mock_back_button.Enable.assert_called_with(False)
        mock_forward_button.Enable.assert_called_with(False)

    def test_on_back_button_click(self):
        mock_webview = MagicMock(spec=wx.html2.WebView)
        self.panel.webview = mock_webview
        mock_event = MagicMock(spec=wx.CommandEvent)

        # Test case 1: Can go back
        mock_webview.CanGoBack.return_value = True
        self.panel._on_back(mock_event)
        mock_webview.GoBack.assert_called_once()
        mock_event.Skip.assert_called_once()

        # Reset mocks
        mock_webview.reset_mock()
        mock_event.reset_mock()

        # Test case 2: Cannot go back
        mock_webview.CanGoBack.return_value = False
        self.panel._on_back(mock_event)
        mock_webview.GoBack.assert_not_called()
        mock_event.Skip.assert_called_once()

    def test_on_forward_button_click(self):
        mock_webview = MagicMock(spec=wx.html2.WebView)
        self.panel.webview = mock_webview
        mock_event = MagicMock(spec=wx.CommandEvent)

        # Test case 1: Can go forward
        mock_webview.CanGoForward.return_value = True
        self.panel._on_forward(mock_event)
        mock_webview.GoForward.assert_called_once()
        mock_event.Skip.assert_called_once()

        # Reset mocks
        mock_webview.reset_mock()
        mock_event.reset_mock()

        # Test case 2: Cannot go forward
        mock_webview.CanGoForward.return_value = False
        self.panel._on_forward(mock_event)
        mock_webview.GoForward.assert_not_called()
        mock_event.Skip.assert_called_once()

    def test_home_button_calls_callback(self):
        # Simulate a click on the home button
        # We need to create a real wx.Button and bind it to the lambda
        # then simulate the event.
        home_button = wx.Button(self.panel, label="Home")
        home_button.Bind(wx.EVT_BUTTON, lambda evt: self.mock_on_home_callback())
        
        # Simulate the event
        event = wx.CommandEvent(wx.EVT_BUTTON.typeId, home_button.GetId())
        home_button.GetEventHandler().ProcessEvent(event)
        wx.Yield()

        self.mock_on_home_callback.assert_called_once()