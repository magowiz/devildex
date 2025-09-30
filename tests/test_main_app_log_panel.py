"""Tests for the log panel visibility logic within the DevilDexApp class."""

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture) -> DevilDexApp:
    """Provide a DevilDexApp instance for testing without a running event loop."""
    mocker.patch("wx.App.__init__", return_value=None)
    mock_core = mocker.MagicMock(name="DevilDexCore")
    app_instance = DevilDexApp(core=mock_core)
    app_instance.panel = mocker.MagicMock(name="MainPanel")
    app_instance.log_toggle_button = mocker.MagicMock(name="LogToggleButton")
    app_instance.splitter = mocker.MagicMock(spec=wx.SplitterWindow)
    mocker.patch("wx.MessageBox")

    return app_instance


def test_on_log_toggle_button_click_toggles_visibility(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify that clicking the toggle button calls the main visibility function."""
    app.is_log_panel_visible = False
    mock_set_visibility = mocker.patch.object(app, "_set_log_panel_visibility")
    mock_event = mocker.MagicMock(spec=wx.CommandEvent)
    app.on_log_toggle_button_click(mock_event)
    mock_set_visibility.assert_called_once_with(True)
    mock_event.Skip.assert_called_once()


def test_set_log_panel_visibility_to_visible(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify the correct helper is called to show the log panel."""
    mock_show_panel = mocker.patch.object(app, "_show_log_panel")
    mock_hide_panel = mocker.patch.object(app, "_hide_log_panel")
    app._set_log_panel_visibility(True)
    assert app.is_log_panel_visible is True
    mock_show_panel.assert_called_once()
    mock_hide_panel.assert_not_called()
    app.panel.Layout.assert_called_once()


def test_set_log_panel_visibility_to_hidden(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify the correct helper is called to hide the log panel."""
    app.is_log_panel_visible = True
    mock_show_panel = mocker.patch.object(app, "_show_log_panel")
    mock_hide_panel = mocker.patch.object(app, "_hide_log_panel")
    app._set_log_panel_visibility(False)
    assert app.is_log_panel_visible is False
    mock_hide_panel.assert_called_once()
    mock_show_panel.assert_not_called()
    app.panel.Layout.assert_called_once()


def test_on_view_log_opens_panel_if_hidden(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify 'View Log' action opens the log panel if it's currently hidden."""
    app.is_log_panel_visible = False
    mocker.patch.object(app, "get_selected_row", return_value={"name": "test"})
    mock_set_visibility = mocker.patch.object(app, "_set_log_panel_visibility")
    mock_event = mocker.MagicMock(spec=wx.CommandEvent)
    app.on_view_log(mock_event)
    mock_set_visibility.assert_called_once_with(True)
    mock_event.Skip.assert_called_once()


def test_on_view_log_does_nothing_if_already_visible(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify 'View Log' action does nothing if the panel is already visible."""
    app.is_log_panel_visible = True
    mocker.patch.object(app, "get_selected_row", return_value={"name": "test"})
    mock_set_visibility = mocker.patch.object(app, "_set_log_panel_visibility")
    mock_event = mocker.MagicMock(spec=wx.CommandEvent)
    app.on_view_log(mock_event)
    mock_set_visibility.assert_not_called()
    mock_event.Skip.assert_called_once()
