"""test main app ui module."""

import wx
import wx.grid
import pytest

from devildex.main import DevilDexApp


@pytest.mark.ui
def test_initial_state_and_title(devildex_app: DevilDexApp):
    """Test the initial state of the main window."""
    frame = devildex_app.main_frame
    assert frame is not None, "Main frame should be created"
    assert frame.IsShown(), "Main frame should be visible"
    assert frame.GetTitle() == "DevilDex", "Window title is incorrect"


@pytest.mark.ui
def test_view_mode_selector_initial_value(devildex_app: DevilDexApp):
    """Test the initial value of the view mode selector ComboBox."""
    view_selector = devildex_app.view_mode_selector
    assert view_selector is not None, "View mode selector should exist"

    simulator = wx.UIActionSimulator()
    simulator.MouseMove(view_selector.GetScreenPosition())
    wx.Yield()

    expected_value = "Show all Docsets (Global)"
    assert view_selector.GetValue() == expected_value, "View mode selector has incorrect initial value"


@pytest.mark.ui
def test_grid_selection_enables_buttons(devildex_app: DevilDexApp):
    """Test that selecting a row in the grid enables the proper action buttons."""
    actions_panel = devildex_app.actions_panel
    assert actions_panel is not None, "Actions panel should exist"

    assert not actions_panel.generate_action_button.IsEnabled(), "Generate button should be disabled initially"
    assert not actions_panel.open_action_button.IsEnabled(), "Open button should be disabled initially"
    assert not actions_panel.regenerate_action_button.IsEnabled(), "Regenerate button should be disabled initially"
    assert not actions_panel.delete_action_button.IsEnabled(), "Delete button should be disabled initially"

    grid_panel = devildex_app.grid_panel
    assert grid_panel is not None, "Grid panel should exist"

    # With the populated database, the grid should have rows.
    grid = grid_panel.grid
    assert grid.GetNumberRows() > 0, "Grid should have rows"

    # Simulate selecting the first row
    class MockGridEvent(wx.grid.GridEvent):
        def __init__(self, row) -> None:
            super().__init__()
            self.m_row = row

        def GetRow(self): 
            return self.m_row

    mock_event = MockGridEvent(row=0)
    grid_panel._on_grid_cell_click(mock_event)
    wx.Yield()

    assert actions_panel.generate_action_button.IsEnabled(), "Generate button should be enabled after selection"
    # The other buttons depend on the docset status, which is 'unknown' by default
    assert not actions_panel.open_action_button.IsEnabled(), "Open button should remain disabled for unavailable docset"
    assert not actions_panel.regenerate_action_button.IsEnabled(), "Regenerate button should be disabled for unavailable docset"
    assert not actions_panel.delete_action_button.IsEnabled(), "Delete button should be disabled for unavailable docset"