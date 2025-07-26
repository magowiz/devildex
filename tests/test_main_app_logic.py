"""Tests for the business logic within the DevilDexApp class.

These tests focus on the application's logic, mocking UI components
and core functionalities to ensure methods behave as expected without
a running GUI.
"""

import pytest
from pytest_mock import MockerFixture

from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture) -> DevilDexApp:
    """Provides a DevilDexApp instance for testing without a running event loop.

    Mocks the wx.App.__init__ to prevent it from starting a real GUI.
    Also mocks the core and UI panel dependencies.
    """
    # Prevent the real wx.App from initializing
    mocker.patch("wx.App.__init__", return_value=None)

    # Mock the core dependency
    mock_core = mocker.MagicMock(name="DevilDexCore")

    # Create the app instance with the mocked core
    app_instance = DevilDexApp(core=mock_core)

    # Attach a mock for the ActionsPanel, as it's a key collaborator
    app_instance.actions_panel = mocker.MagicMock(name="ActionsPanel")

    return app_instance


@pytest.mark.parametrize(
    "package_data, is_task_running, case_id",
    [
        (None, False, "no_selection"),
        ({"name": "test-package"}, True, "selection_with_task_running"),
        ({"name": "test-package"}, False, "selection_no_task"),
    ],
    ids=lambda x: x if isinstance(x, str) else "",
)
def test_update_action_buttons_state_delegates_correctly(
    app: DevilDexApp,
    mocker: MockerFixture,
    package_data: dict | None,
    is_task_running: bool,
    case_id: str,
):
    """Verify that _update_action_buttons_state correctly calls the
    ActionsPanel with the current state.
    """
    # Arrange
    # We simulate the app having a selected row by mocking get_selected_row
    mocker.patch.object(app, "get_selected_row", return_value=package_data)
    app.is_task_running = is_task_running
    mock_actions_panel = app.actions_panel

    # Act
    app._update_action_buttons_state()

    # Assert
    # We just need to check that the app correctly told the panel to update itself
    mock_actions_panel.update_button_states.assert_called_once_with(
        package_data, is_task_running
    )
