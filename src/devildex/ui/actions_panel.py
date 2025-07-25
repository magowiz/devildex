"""Custom wx.Panel component for the docset action buttons."""

from typing import Any, Protocol

import wx
from wx import Size

from devildex.constants import (
    AVAILABLE_BTN_LABEL,
    ERROR_BTN_LABEL,
    NOT_AVAILABLE_BTN_LABEL,
)


class ActionHandler(Protocol):
    """Define the contract for methods that handle actions from this panel."""

    def on_open_docset(self, event: wx.CommandEvent) -> None:
        """Handle the 'Open Docset' action."""

    def on_generate_docset(self, event: wx.CommandEvent | None) -> None:
        """Handle the 'Generate Docset' action."""

    def on_regenerate_docset(self, event: wx.CommandEvent) -> None:
        """Handle the 'Regenerate Docset' action."""

    def on_view_log(self, event: wx.CommandEvent) -> None:
        """Handle the 'View Error Log' action."""

    def on_delete_docset(self, event: wx.CommandEvent | None) -> None:
        """Handle the 'Delete Docset' action."""


class ActionsPanel(wx.Panel):
    """A panel that encapsulates all the docset action buttons and their logic."""

    def __init__(self, parent: wx.Window, handlers: ActionHandler) -> None:
        """Initialize the ActionsPanel.

        Args:
            parent: The parent window.
            handlers: An object that provides the methods to handle button events.

        """
        super().__init__(parent)

        self.handlers = handlers

        self.open_action_button: wx.Button | None = None
        self.generate_action_button: wx.Button | None = None
        self.regenerate_action_button: wx.Button | None = None
        self.view_log_action_button: wx.Button | None = None
        self.delete_action_button: wx.Button | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create and arrange the widgets in the panel."""
        action_box = wx.StaticBox(self, label="Docset Actions")
        static_box_sizer = wx.StaticBoxSizer(action_box, wx.VERTICAL)
        buttons_internal_sizer = wx.BoxSizer(wx.VERTICAL)

        button_definitions = [
            (
                "Open Docset",
                wx.ART_FILE_OPEN,
                "open_action_button",
                self.handlers.on_open_docset,
            ),
            (
                "Generate Docset",
                wx.ART_NEW,
                "generate_action_button",
                self.handlers.on_generate_docset,
            ),
            (
                "Regenerate Docset",
                wx.ART_REDO,
                "regenerate_action_button",
                self.handlers.on_regenerate_docset,
            ),
            (
                "View Error Log",
                wx.ART_REPORT_VIEW,
                "view_log_action_button",
                self.handlers.on_view_log,
            ),
            (
                "Delete Docset",
                wx.ART_DELETE,
                "delete_action_button",
                self.handlers.on_delete_docset,
            ),
        ]

        for label_text, art_id, attr_name, handler in button_definitions:
            button = wx.Button(action_box, label=label_text, style=wx.BU_LEFT)
            self._set_button_icon(button, art_id)
            setattr(self, attr_name, button)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons_internal_sizer.Add(button, 0, wx.EXPAND | wx.ALL, 5)
            button.Enable(False)

        static_box_sizer.Add(buttons_internal_sizer, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizerAndFit(static_box_sizer)

    def update_button_states(
        self, package_data: dict[str, Any] | None, is_task_running: bool
    ) -> None:
        """Update the state of the action buttons based on external state.

        This is the public API for this panel.

        Args:
            package_data: The data for the currently selected package, or None.
            is_task_running: True if any generation task is currently active.

        """
        if not package_data:
            for button in [
                self.open_action_button,
                self.generate_action_button,
                self.regenerate_action_button,
                self.view_log_action_button,
                self.delete_action_button,
            ]:
                if button:
                    button.Enable(False)
            return

        current_docset_status = package_data.get(
            "docset_status", NOT_AVAILABLE_BTN_LABEL
        )
        is_generating_this_row = is_task_running

        if self.open_action_button:
            can_open = (
                current_docset_status == AVAILABLE_BTN_LABEL
                and not is_generating_this_row
            )
            self.open_action_button.Enable(can_open)

        if self.generate_action_button:
            can_generate = (
                not is_generating_this_row
                and current_docset_status != AVAILABLE_BTN_LABEL
            )
            self.generate_action_button.Enable(can_generate)

        can_regenerate_or_delete = (
            not is_generating_this_row
            and current_docset_status in [AVAILABLE_BTN_LABEL, ERROR_BTN_LABEL]
        )
        if self.regenerate_action_button:
            self.regenerate_action_button.Enable(can_regenerate_or_delete)
        if self.delete_action_button:
            self.delete_action_button.Enable(can_regenerate_or_delete)
        if self.view_log_action_button:
            self.view_log_action_button.Enable(True)

    @staticmethod
    def _set_button_icon(button: wx.Button, art_id: str) -> None:
        """Apply a standard icon to a button, aligned to the left."""
        bitmap = wx.ArtProvider.GetBitmap(art_id, wx.ART_BUTTON)
        if bitmap.IsOk():
            bundle = wx.BitmapBundle(bitmap)
            button.SetBitmap(bundle, wx.LEFT)
            button.SetBitmapMargins(Size(4, 0))
