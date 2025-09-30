"""settings panel module."""

import logging
from typing import Callable

import wx

from devildex.config_manager import ConfigManager

MIN_PORT_NUMBER = 1024
MAX_PORT_NUMBER = 65535

logger = logging.getLogger(__name__)


class SettingsPanel(wx.Panel):
    """Settings Panel class."""

    def __init__(
        self,
        parent: wx.Window,
        on_save_callback: Callable,
        on_cancel_callback: Callable,
    ) -> None:
        """Initialize the SettingsPanel."""
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.on_save_callback = on_save_callback
        self.on_cancel_callback = on_cancel_callback

        self._init_ui()
        self._load_settings()

    def _init_ui(self) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        title = wx.StaticText(self, label="MCP Server Settings")
        title_font = wx.Font(
            14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)
        settings_box = wx.StaticBoxSizer(
            wx.StaticBox(self, label="MCP Server Configuration"), wx.VERTICAL
        )
        warning_panel = wx.Panel(self, style=wx.BORDER_SIMPLE)
        warning_panel.SetBackgroundColour(wx.Colour(255, 255, 204))
        warning_sizer = wx.BoxSizer(wx.HORIZONTAL)
        warning_icon = wx.StaticBitmap(
            warning_panel,
            wx.ID_ANY,
            wx.ArtProvider.GetBitmap(
                wx.ART_WARNING, wx.ART_MESSAGE_BOX, wx.Size(24, 24)
            ),
        )
        warning_sizer.Add(warning_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        warning_text_content = (
            "WARNING: The MCP server is currently experimental in "
            "all modes (GUI and headless). "
            "It has limited functionality and is primarily for development and testing."
            " Use with caution."
        )
        warning_label = wx.StaticText(
            warning_panel, label=warning_text_content, style=wx.ALIGN_LEFT
        )
        bold_font = wx.Font(
            10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        warning_label.SetFont(bold_font)
        warning_label.SetForegroundColour(wx.BLACK)

        warning_sizer.Add(warning_label, 1, wx.ALL | wx.EXPAND, 5)
        warning_panel.SetSizer(warning_sizer)

        settings_box.Add(warning_panel, 0, wx.EXPAND | wx.ALL, 5)

        settings_grid_sizer = wx.FlexGridSizer(cols=2, hgap=10, vgap=10)
        settings_grid_sizer.AddGrowableCol(1)
        settings_grid_sizer.Add(
            wx.StaticText(self, label="Enable MCP Server:"), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.enabled_checkbox = wx.CheckBox(self)
        settings_grid_sizer.Add(self.enabled_checkbox, 0, wx.EXPAND)
        settings_grid_sizer.Add(
            wx.StaticText(self, label="Hide GUI when enabled:"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.hide_gui_checkbox = wx.CheckBox(self)
        settings_grid_sizer.Add(self.hide_gui_checkbox, 0, wx.EXPAND)
        settings_grid_sizer.Add(
            wx.StaticText(self, label="Port:"), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.port_text_ctrl = wx.TextCtrl(self)
        settings_grid_sizer.Add(self.port_text_ctrl, 0, wx.EXPAND)

        settings_box.Add(settings_grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(settings_box, 0, wx.ALL | wx.EXPAND, 10)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_button = wx.Button(self, label="Save")
        cancel_button = wx.Button(self, label="Cancel")

        save_button.Bind(wx.EVT_BUTTON, self._on_save)
        cancel_button.Bind(wx.EVT_BUTTON, self._on_cancel)

        button_sizer.Add(save_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)

        self.SetSizerAndFit(main_sizer)

    def _load_settings(self) -> None:
        self.enabled_checkbox.SetValue(self.config_manager.get_mcp_server_enabled())
        self.hide_gui_checkbox.SetValue(
            self.config_manager.get_mcp_server_hide_gui_when_enabled()
        )
        self.port_text_ctrl.SetValue(str(self.config_manager.get_mcp_server_port()))

    def _on_save(self, _event: wx.Event) -> None:
        try:
            port = int(self.port_text_ctrl.GetValue())
            if not (MIN_PORT_NUMBER <= port <= MAX_PORT_NUMBER):
                wx.MessageBox(
                    "Port number must be between 1024 and 65535.",
                    "Invalid Port",
                    wx.OK | wx.ICON_ERROR,
                )
                return
            self.config_manager.set_mcp_server_enabled(self.enabled_checkbox.GetValue())
            self.config_manager.set_mcp_server_hide_gui_when_enabled(
                self.hide_gui_checkbox.GetValue()
            )
            self.config_manager.set_mcp_server_port(port)
            self.config_manager.save_config()
            logger.info("MCP Server settings saved.")
            self.on_save_callback()
        except ValueError:
            wx.MessageBox(
                "Invalid port number. Please enter a valid integer.",
                "Input Error",
                wx.OK | wx.ICON_ERROR,
            )
        except Exception as e:
            logger.exception("Error saving settings")
            wx.MessageBox(
                f"An error occurred while saving settings: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_cancel(self, _event: wx.Event) -> None:
        logger.info("MCP Server settings cancelled.")
        self.on_cancel_callback()
