import unittest
import wx

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
        # We need a running DevilDexCore for the app to initialize correctly
        self.core = DevilDexCore(database_url='sqlite:///:memory:')
        # Initialize the application. The OnInit method will be called, creating the frame.
        self.app = DevilDexApp(core=self.core)

        # Process pending events to ensure the UI is fully constructed
        wx.Yield()

        self.frame = self.app.main_frame
        self.simulator = wx.UIActionSimulator()

    def tearDown(self):
        """Tear down the test environment."""
        # We need to be careful with the event loop and destroying frames.
        # wx.CallAfter ensures that the frame is destroyed after the current event handler has completed.
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
        self.assertEqual(view_selector.GetValue(), expected_value, "View mode selector has incorrect initial value")

if __name__ == '__main__':
    unittest.main()
