"""Tests for the ActionsPanel UI component logic."""

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.constants import (
    AVAILABLE_BTN_LABEL,
    ERROR_BTN_LABEL,
    NOT_AVAILABLE_BTN_LABEL,
)
from devildex.ui.actions_panel import ActionHandler, ActionsPanel


@pytest.fixture(scope="module")
def wx_app() -> wx.App:
    """Fixture to create a wx.App instance, required for creating wx.Panel."""
    app = wx.App(False)
    return app


@pytest.fixture
def mock_handler(mocker: MockerFixture) -> ActionHandler:
    """Provide a mock handler for the ActionsPanel."""
    return mocker.MagicMock(spec=ActionHandler)


@pytest.fixture
def actions_panel(
    wx_app: wx.App, mock_handler: ActionHandler, mocker: MockerFixture
) -> ActionsPanel:
    """Provide an instance of ActionsPanel for testing.

    Mocks the Enable() method on each button to allow tracking calls.
    """
    frame = wx.Frame(wx_app.GetTopWindow())
    panel = ActionsPanel(frame, mock_handler)

    for button_attr in [
        "open_action_button",
        "generate_action_button",
        "regenerate_action_button",
        "view_log_action_button",
        "delete_action_button",
    ]:
        button = getattr(panel, button_attr)
        if button:
            button.Enable = mocker.MagicMock(name=f"{button_attr}.Enable")

    frame.Destroy()
    return panel


test_cases = [
    (
        None,
        False,
        {
            "open": False,
            "generate": False,
            "regenerate": False,
            "view_log": False,
            "delete": False,
        },
        "no_selection",
    ),
    (
        {"docset_status": "Generating..."},
        True,
        {
            "open": False,
            "generate": False,
            "regenerate": False,
            "view_log": True,
            "delete": False,
        },
        "task_is_running",
    ),
    (
        {"docset_status": AVAILABLE_BTN_LABEL},
        False,
        {
            "open": True,
            "generate": False,
            "regenerate": True,
            "view_log": True,
            "delete": True,
        },
        "status_available",
    ),
    (
        {"docset_status": NOT_AVAILABLE_BTN_LABEL},
        False,
        {
            "open": False,
            "generate": True,
            "regenerate": False,
            "view_log": True,
            "delete": False,
        },
        "status_not_available",
    ),
    (
        {"docset_status": ERROR_BTN_LABEL},
        False,
        {
            "open": False,
            "generate": True,
            "regenerate": True,
            "view_log": True,
            "delete": True,
        },
        "status_error",
    ),
]


@pytest.mark.ui
@pytest.mark.parametrize(
    ("package_data", "is_task_running", "expected_states", "test_id"),
    test_cases,
    ids=[case[3] for case in test_cases],
)
def test_update_button_states(
    actions_panel: ActionsPanel,
    package_data: dict | None,
    is_task_running: bool,
    expected_states: dict[str, bool],
    test_id: str,
) -> None:
    """Verify that button states are updated correctly based on package status."""
    _ = test_id
    actions_panel.update_button_states(package_data, is_task_running)
    actions_panel.open_action_button.Enable.assert_called_once_with(
        expected_states["open"]
    )
    actions_panel.generate_action_button.Enable.assert_called_once_with(
        expected_states["generate"]
    )
    actions_panel.regenerate_action_button.Enable.assert_called_once_with(
        expected_states["regenerate"]
    )
    actions_panel.view_log_action_button.Enable.assert_called_once_with(
        expected_states["view_log"]
    )
    actions_panel.delete_action_button.Enable.assert_called_once_with(
        expected_states["delete"]
    )
