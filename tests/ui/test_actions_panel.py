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
    """Provides a mock handler for the ActionsPanel."""
    return mocker.MagicMock(spec=ActionHandler)


@pytest.fixture
def actions_panel(
    wx_app: wx.App, mock_handler: ActionHandler, mocker: MockerFixture
) -> ActionsPanel:
    """
    Provides an instance of ActionsPanel for testing.

    Mocks the Enable() method on each button to allow tracking calls.
    """
    # A dummy frame is needed as a parent for the panel
    frame = wx.Frame(None)
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
            # Replace the real Enable method with a mock
            button.Enable = mocker.MagicMock(name=f"{button_attr}.Enable")

    frame.Destroy()
    return panel


# --- Test Cases ---

test_cases = [
    # 1. No package selected
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
    # 2. Task is running for the selected row
    (
        {"docset_status": "Generating..."},
        True,  # Task is running
        {
            "open": False,
            "generate": False,
            "regenerate": False,
            "view_log": True,
            "delete": False,
        },
        "task_is_running",
    ),
    # 3. Docset is 'Available'
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
    # 4. Docset is 'Not Available'
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
    # 5. Docset is in 'Error' state
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


@pytest.mark.parametrize(
    "package_data, is_task_running, expected_states, test_id",
    test_cases,
    ids=[case[3] for case in test_cases],
)
def test_update_button_states(
    actions_panel: ActionsPanel,
    package_data: dict | None,
    is_task_running: bool,
    expected_states: dict[str, bool],
    test_id: str,  # FIX: Add the missing parameter
):
    """Verify that button states are updated correctly based on package and task status."""
    # The 'test_id' parameter is intentionally unused in the function body.
    # It's only here to match the parametrize signature.
    _ = test_id

    # Act
    actions_panel.update_button_states(package_data, is_task_running)

    # Assert
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
