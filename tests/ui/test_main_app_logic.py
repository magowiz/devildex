"""test main app ui module."""

import unittest
from unittest.mock import MagicMock, patch

import pytest
import wx
import wx.grid

app = wx.GetApp()
if app is None:
    app = wx.App(redirect=False)

from devildex.core import DevilDexCore  # noqa: E402
from devildex.main import DevilDexApp  # noqa: E402


@pytest.mark.ui
class TestMainAppLogic(unittest.TestCase):
    """Test the main application UI logic and interactions."""

    def setUp(self) -> None:
        """Set up the test environment."""
        self.patcher = patch("devildex.main.GenerationTaskManager")
        self.mock_gen_task_manager_cls = self.patcher.start()
        self.mock_gen_task_manager_instance = (
            self.mock_gen_task_manager_cls.return_value
        )

        self.mock_core = MagicMock(spec=DevilDexCore)
        self.mock_core.scan_project.return_value = []
        self.mock_core.bootstrap_database_and_load_data.return_value = []
        self.mock_core.list_package_dirs.return_value = []
        self.mock_core.app_paths = MagicMock()
        self.mock_core.app_paths.active_project_file = MagicMock()
        self.mock_core.app_paths.active_project_file.unlink = MagicMock()

        self.app = DevilDexApp(core=self.mock_core)
        self.app.OnInit()  # Manually call OnInit for testing setup

        wx.Yield()

        self.frame = self.app.main_frame
        self.simulator = wx.UIActionSimulator()

    def tearDown(self) -> None:
        """Tear down the test environment."""
        self.patcher.stop()
        if self.frame:
            wx.CallAfter(self.frame.Destroy)
        wx.Yield()

    def test_on_init_initial_state(self) -> None:
        """Verify the initial state of the UI after OnInit."""
        assert self.frame is not None, "Main frame should be created"
        assert self.frame.IsShown(), "Main frame should be visible"
        assert self.frame.GetTitle() == "DevilDex", "Window title is incorrect"
        assert self.app.grid_panel is not None, "Grid panel should be initialized"
        assert self.app.actions_panel is not None, "Actions panel should be initialized"
        assert (
            self.app.view_mode_selector is not None
        ), "View mode selector should be initialized"
        assert (
            self.app.log_toggle_button is not None
        ), "Log toggle button should be initialized"
        assert not self.app.is_log_panel_visible, "Log panel should be hidden initially"

    def test_on_log_toggle_button_click(self) -> None:
        """Test toggling the log panel visibility."""
        assert not self.app.is_log_panel_visible
        assert not (self.app.bottom_splitter_panel.IsShown())

        self.app.on_log_toggle_button_click(wx.CommandEvent())
        wx.Yield()
        assert self.app.is_log_panel_visible
        assert self.app.bottom_splitter_panel.IsShown()

        self.app.on_log_toggle_button_click(wx.CommandEvent())
        wx.Yield()
        assert not self.app.is_log_panel_visible
        assert not (self.app.bottom_splitter_panel.IsShown())


if __name__ == "__main__":
    unittest.main()
