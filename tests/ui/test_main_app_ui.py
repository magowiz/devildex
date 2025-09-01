"""test main app ui module."""
import unittest
from unittest.mock import patch

import wx
import wx.grid

# It's crucial to have a wx.App instance for any UI testing.
# We'll create one for the whole test suite if it doesn't exist.
app = wx.GetApp()
if app is None:
    app = wx.App(redirect=False)

from devildex.core import DevilDexCore
from devildex.main import DevilDexApp


class TestMainAppUI(unittest.TestCase):
    """Test the main application UI using UIActionSimulator."""

    def setUp(self):
        """Set up the test environment."""
        self.patcher = patch("devildex.main.GenerationTaskManager")
        self.mock_gen_task_manager_cls = self.patcher.start()
        self.mock_gen_task_manager_instance = (
            self.mock_gen_task_manager_cls.return_value
        )

        self.core = DevilDexCore(database_url="sqlite:///:memory:")
        self.app = DevilDexApp(core=self.core)

        # Process pending events to ensure the UI is fully constructed
        wx.Yield()

        self.frame = self.app.main_frame
        self.simulator = wx.UIActionSimulator()

    def tearDown(self):
        """Tear down the test environment."""
        self.patcher.stop()
        if self.frame:
            wx.CallAfter(self.frame.Destroy)

        # Process events to ensure cleanup is done
        wx.Yield()

    def test_initial_state_and_title(self):
        """Test the initial state of the main window."""
        self.assertIsNotNone(self.frame, "Main frame should be created")
        self.assertTrue(self.frame.IsShown(), "Main frame should be visible")
        self.assertEqual(self.frame.GetTitle(), "DevilDex", "Window title is incorrect")

    def test_view_mode_selector_initial_value(self):
        """Test the initial value of the view mode selector ComboBox."""
        view_selector = self.app.view_mode_selector
        self.assertIsNotNone(view_selector, "View mode selector should exist")

        # Simulate a mouse move to the widget to ensure it's 'active'
        self.simulator.MouseMove(view_selector.GetScreenPosition())
        wx.Yield()

        expected_value = "Show all Docsets (Global)"
        self.assertEqual(
            view_selector.GetValue(),
            expected_value,
            "View mode selector has incorrect initial value",
        )

    def test_grid_selection_enables_buttons(self):
        """Test that selecting a row in the grid enables the proper action buttons."""
        actions_panel = self.app.actions_panel
        self.assertIsNotNone(actions_panel, "Actions panel should exist")

        self.assertFalse(
            actions_panel.generate_action_button.IsEnabled(),
            "Generate button should be disabled initially",
        )
        self.assertFalse(
            actions_panel.open_action_button.IsEnabled(),
            "Open button should be disabled initially",
        )
        self.assertFalse(
            actions_panel.regenerate_action_button.IsEnabled(),
            "Regenerate button should be disabled initially",
        )
        self.assertFalse(
            actions_panel.delete_action_button.IsEnabled(),
            "Delete button should be disabled initially",
        )

        grid_panel = self.app.grid_panel
        self.assertIsNotNone(grid_panel, "Grid panel should exist")

        class MockGridEvent(wx.grid.GridEvent):
            def __init__(self, row):
                super().__init__()
                self.m_row = row

            def GetRow(self):
                return self.m_row

        mock_event = MockGridEvent(row=0)
        grid_panel._on_grid_cell_click(mock_event)

        wx.Yield()

        self.assertTrue(
            actions_panel.generate_action_button.IsEnabled(),
            "Generate button should be enabled after selection",
        )
        self.assertFalse(
            actions_panel.open_action_button.IsEnabled(),
            "Open button should remain disabled for unavailable docset",
        )
        self.assertFalse(
            actions_panel.regenerate_action_button.IsEnabled(),
            "Regenerate button should be disabled for unavailable docset",
        )
        self.assertFalse(
            actions_panel.delete_action_button.IsEnabled(),
            "Delete button should be disabled for unavailable docset",
        )

    def test_generate_docset_button_starts_task(self):
        """Test that clicking the Generate Docset button starts a generation task."""
        actions_panel = self.app.actions_panel
        grid_panel = self.app.grid_panel

        # 1. Select a row to enable the generate button
        class MockGridEvent(wx.grid.GridEvent):
            def __init__(self, row):
                super().__init__()
                self.m_row = row

            def GetRow(self):
                return self.m_row

        mock_event = MockGridEvent(row=0)  # Select the first package (e.g., 'black')
        grid_panel._on_grid_cell_click(mock_event)
        wx.Yield()

        # Ensure the button is enabled before clicking
        self.assertTrue(
            actions_panel.generate_action_button.IsEnabled(),
            "Generate button should be enabled after selection",
        )

        # Configure the mock to return False for is_task_active_for_package
        self.mock_gen_task_manager_instance.is_task_active_for_package.return_value = (
            False
        )

        # 2. Simulate click on the Generate Docset button
        generate_button = actions_panel.generate_action_button
        self.assertIsNotNone(generate_button, "Generate button should exist")

        # Simulate a click by calling the handler directly
        generate_button.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId, generate_button.GetId())
        )
        wx.Yield()

        self.mock_gen_task_manager_instance.start_generation_task.assert_called_once()
        call_args, call_kwargs = (
            self.mock_gen_task_manager_instance.start_generation_task.call_args
        )
        self.assertIn("package_data", call_kwargs)
        self.assertEqual(call_kwargs["row_index"], 0)
        self.assertEqual(
            call_kwargs["docset_status_col_idx"], 6
        )  # Based on COLUMNS_ORDER in constants.py
        self.assertEqual(call_kwargs["package_data"]["name"], "black")


if __name__ == "__main__":
    unittest.main()
