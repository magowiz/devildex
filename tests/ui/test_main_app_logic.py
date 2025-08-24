import unittest
import wx
import wx.grid
from unittest.mock import patch, MagicMock
import pytest

# It's crucial to have a wx.App instance for any UI testing.
# We'll create one for the whole test suite if it doesn't exist.
app = wx.GetApp()
if app is None:
    app = wx.App(redirect=False)

from devildex.core import DevilDexCore
from devildex.main import DevilDexApp

@pytest.mark.ui
class TestMainAppLogic(unittest.TestCase):
    """Test the main application UI logic and interactions."""

    def setUp(self):
        """Set up the test environment."""
        self.patcher = patch('devildex.main.GenerationTaskManager')
        self.mock_gen_task_manager_cls = self.patcher.start()
        self.mock_gen_task_manager_instance = self.mock_gen_task_manager_cls.return_value

        # Mock DevilDexCore to control its behavior
        self.mock_core = MagicMock(spec=DevilDexCore)
        self.mock_core.scan_project.return_value = [] # No projects found initially
        self.mock_core.bootstrap_database_and_load_data.return_value = [] # No data initially
        self.mock_core.list_package_dirs.return_value = [] # No docset dirs initially
        self.mock_core.app_paths = MagicMock()
        self.mock_core.app_paths.active_project_file = MagicMock()
        self.mock_core.app_paths.active_project_file.unlink = MagicMock()

        # Initialize the application. The OnInit method will be called, creating the frame.
        self.app = DevilDexApp(core=self.mock_core)
        self.app.OnInit() # Manually call OnInit for testing setup

        # Process pending events to ensure the UI is fully constructed
        wx.Yield()

        self.frame = self.app.main_frame
        self.simulator = wx.UIActionSimulator()

    def tearDown(self):
        """Tear down the test environment."""
        self.patcher.stop()
        if self.frame:
            wx.CallAfter(self.frame.Destroy)
        wx.Yield()

    def test_on_init_initial_state(self):
        """Verify the initial state of the UI after OnInit."""
        self.assertIsNotNone(self.frame, "Main frame should be created")
        self.assertTrue(self.frame.IsShown(), "Main frame should be visible")
        self.assertEqual(self.frame.GetTitle(), "DevilDex", "Window title is incorrect")
        self.assertIsNotNone(self.app.grid_panel, "Grid panel should be initialized")
        self.assertIsNotNone(self.app.actions_panel, "Actions panel should be initialized")
        self.assertIsNotNone(self.app.view_mode_selector, "View mode selector should be initialized")
        self.assertIsNotNone(self.app.log_toggle_button, "Log toggle button should be initialized")
        self.assertFalse(self.app.is_log_panel_visible, "Log panel should be hidden initially")

    def test_on_log_toggle_button_click(self):
        """Test toggling the log panel visibility."""
        # Initial state: log panel is hidden
        self.assertFalse(self.app.is_log_panel_visible)
        self.assertFalse(self.app.bottom_splitter_panel.IsShown())

        # Simulate click to show log panel
        self.app.on_log_toggle_button_click(wx.CommandEvent())
        wx.Yield()
        self.assertTrue(self.app.is_log_panel_visible)
        self.assertTrue(self.app.bottom_splitter_panel.IsShown())

        # Simulate click to hide log panel
        self.app.on_log_toggle_button_click(wx.CommandEvent())
        wx.Yield()
        self.assertFalse(self.app.is_log_panel_visible)
        self.assertFalse(self.app.bottom_splitter_panel.IsShown())

if __name__ == '__main__':
    unittest.main()
