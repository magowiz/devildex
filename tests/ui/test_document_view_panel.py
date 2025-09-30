"""Tests for the DocumentViewPanel UI component logic."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import wx
import wx.html2

from devildex.ui.document_view_panel import DocumentViewPanel


@pytest.fixture
def document_view_panel(
    wx_app: wx.App, mocker: MagicMock
) -> Generator[tuple[DocumentViewPanel, MagicMock]]:
    """Fixture to provide an instance of DocumentViewPanel for testing."""
    frame = wx.Frame(wx_app.GetTopWindow())
    mock_on_home_callback = mocker.MagicMock()
    panel = DocumentViewPanel(frame, mock_on_home_callback)
    wx.Yield()
    yield panel, mock_on_home_callback
    if frame:
        wx.CallAfter(frame.Destroy)
    wx.Yield()


class TestDocumentViewPanel:
    """Test class for DocumentViewPanel."""

    def test_initialization(self, document_view_panel: DocumentViewPanel) -> None:
        """Test initialization of DocumentViewPanel."""
        panel, mock_on_home_callback = document_view_panel
        assert isinstance(panel, DocumentViewPanel)
        assert panel.webview is not None
        assert panel.back_button is not None
        assert panel.forward_button is not None
        assert panel.home_button is not None
        assert panel.package_display_label is not None
        assert panel.on_home_callback == mock_on_home_callback

    def test_setup_ui_elements(self, document_view_panel: DocumentViewPanel) -> None:
        """Test setup ui elements."""
        panel, _ = document_view_panel
        assert isinstance(panel.webview, wx.html2.WebView)

        assert isinstance(panel.package_display_label, wx.StaticText)
        assert panel.package_display_label.GetLabel() == "Loading document..."
        assert panel.package_display_label.GetFont().GetWeight() == wx.FONTWEIGHT_BOLD

        assert isinstance(panel.back_button, wx.Button)
        assert isinstance(panel.forward_button, wx.Button)
        assert isinstance(panel.home_button, wx.Button)

    def test_load_url(self, document_view_panel: DocumentViewPanel) -> None:
        """Test load url ui."""
        panel, _ = document_view_panel
        with patch.object(panel.webview, "LoadURL") as mock_load_url:
            test_url = "https://example.com"
            panel.load_url(test_url)
            mock_load_url.assert_called_once_with(test_url)

    def test_set_document_title(self, document_view_panel: DocumentViewPanel) -> None:
        """Test document title ui."""
        panel, _ = document_view_panel
        mock_label = MagicMock(spec=wx.StaticText)
        panel.package_display_label = mock_label
        test_title = "My Test Document"
        panel.set_document_title(test_title)
        mock_label.SetLabel.assert_called_once_with(test_title)

    def test_update_navigation_buttons_state(
        self, document_view_panel: DocumentViewPanel
    ) -> None:
        """Test navigation buttons ui."""
        panel, _ = document_view_panel
        with (
            patch.object(panel.webview, "CanGoBack") as mock_can_go_back,
            patch.object(panel.webview, "CanGoForward") as mock_can_go_forward,
        ):

            mock_back_button = MagicMock(spec=wx.Button)
            mock_forward_button = MagicMock(spec=wx.Button)

            panel.back_button = mock_back_button
            panel.forward_button = mock_forward_button

            mock_can_go_back.return_value = True
            mock_can_go_forward.return_value = True
            panel.update_navigation_buttons_state()
            mock_back_button.Enable.assert_called_with(True)
            mock_forward_button.Enable.assert_called_with(True)

            mock_back_button.reset_mock()
            mock_forward_button.reset_mock()

            mock_can_go_back.return_value = False
            mock_can_go_forward.return_value = False
            panel.update_navigation_buttons_state()
            mock_back_button.Enable.assert_called_with(False)
            mock_forward_button.Enable.assert_called_with(False)

    def test_on_back_button_click(self, document_view_panel: DocumentViewPanel) -> None:
        """Test back button ui."""
        panel, _ = document_view_panel
        with (
            patch.object(panel.webview, "CanGoBack") as mock_can_go_back,
            patch.object(panel.webview, "GoBack") as mock_go_back,
        ):

            mock_event = MagicMock(spec=wx.CommandEvent)

            mock_can_go_back.return_value = True
            panel._on_back(mock_event)
            mock_go_back.assert_called_once()
            mock_event.Skip.assert_called_once()

            mock_can_go_back.reset_mock()
            mock_go_back.reset_mock()
            mock_event.reset_mock()

            mock_can_go_back.return_value = False
            panel._on_back(mock_event)
            mock_go_back.assert_not_called()
            mock_event.Skip.assert_called_once()

    def test_on_forward_button_click(
        self, document_view_panel: DocumentViewPanel
    ) -> None:
        """Test forward button ui."""
        panel, _ = document_view_panel
        with (
            patch.object(panel.webview, "CanGoForward") as mock_can_go_forward,
            patch.object(panel.webview, "GoForward") as mock_go_forward,
        ):

            mock_event = MagicMock(spec=wx.CommandEvent)
            mock_can_go_forward.return_value = True
            panel._on_forward(mock_event)
            mock_go_forward.assert_called_once()
            mock_event.Skip.assert_called_once()
            mock_can_go_forward.reset_mock()
            mock_go_forward.reset_mock()
            mock_event.reset_mock()
            mock_can_go_forward.return_value = False
            panel._on_forward(mock_event)
            mock_go_forward.assert_not_called()
            mock_event.Skip.assert_called_once()

    def test_home_button_calls_callback(
        self, document_view_panel: DocumentViewPanel
    ) -> None:
        """Test home button ui."""
        panel, mock_on_home_callback = document_view_panel
        home_button = wx.Button(panel, label="Home")
        home_button.Bind(wx.EVT_BUTTON, lambda evt: mock_on_home_callback())

        event = wx.CommandEvent(wx.EVT_BUTTON.typeId, home_button.GetId())
        home_button.GetEventHandler().ProcessEvent(event)
        wx.Yield()

        mock_on_home_callback.assert_called_once()
