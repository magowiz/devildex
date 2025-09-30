"""Tests for the business logic within the DevilDexApp class.

These tests focus on the application's logic, mocking UI components
and core functionalities to ensure methods behave as expected without
a running GUI.
"""

from pathlib import Path

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.constants import AVAILABLE_BTN_LABEL
from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture) -> DevilDexApp:
    """Provide a DevilDexApp instance for testing without a running event loop.

    Mocks the wx.App.__init__ to prevent it from starting a real GUI.
    Also mocks the core and UI panel dependencies.
    """
    mocker.patch("wx.App.__init__", return_value=None)
    mock_core = mocker.MagicMock(name="DevilDexCore")
    app_instance = DevilDexApp(core=mock_core)
    app_instance.actions_panel = mocker.MagicMock(name="ActionsPanel")
    mocker.patch("wx.MessageBox")
    return app_instance


@pytest.mark.parametrize(
    ("package_data", "is_task_running", "case_id"),
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
) -> None:
    """Verify that _update_action_buttons_state correctly calls the AP.

    ActionsPanel with the current state.
    """
    mocker.patch.object(app, "get_selected_row", return_value=package_data)
    app.is_task_running = is_task_running
    mock_actions_panel = app.actions_panel
    app._update_action_buttons_state()
    mock_actions_panel.update_button_states.assert_called_once_with(
        package_data, is_task_running
    )


def test_on_delete_docset_success(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify the full success path for deleting a docset."""
    selected_data = {"name": "test-package", "docset_path": "/fake/path/docset"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_confirm_deletion", return_value=True)
    app.core.delete_docset_build.return_value = (True, "Success")
    mock_handle_success = mocker.patch.object(app, "_handle_delete_success")
    mock_update_buttons = mocker.patch.object(app, "_update_action_buttons_state")
    app.on_delete_docset(event=None)
    app.core.delete_docset_build.assert_called_once_with("/fake/path/docset")
    mock_handle_success.assert_called_once_with("test-package")
    mock_update_buttons.assert_called_once()


def test_on_delete_docset_user_cancels(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify nothing happens if the user cancels the deletion."""
    selected_data = {"name": "test-package", "docset_path": "/fake/path/docset"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_confirm_deletion", return_value=False)
    app.on_delete_docset(event=None)
    app.core.delete_docset_build.assert_not_called()


def test_on_delete_docset_core_fails(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify the failure path is handled when the core cannot delete."""
    selected_data = {"name": "test-package", "docset_path": "/fake/path/docset"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_confirm_deletion", return_value=True)
    app.core.delete_docset_build.return_value = (False, "Permission denied")
    mock_handle_failure = mocker.patch.object(app, "_handle_delete_failure")
    mock_update_buttons = mocker.patch.object(app, "_update_action_buttons_state")
    app.on_delete_docset(event=None)
    app.core.delete_docset_build.assert_called_once_with("/fake/path/docset")
    mock_handle_failure.assert_called_once_with("test-package", "Permission denied")
    mock_update_buttons.assert_called_once()


def test_on_delete_docset_no_path_in_data(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify it shows a message box if the selected package has no path."""
    selected_data = {"name": "test-package"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    app.on_delete_docset(event=None)
    wx.MessageBox.assert_called_once()
    assert "No docset path found" in wx.MessageBox.call_args[0][0]
    app.core.delete_docset_build.assert_not_called()


def test_on_generate_docset_success(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify the success path for starting a docset generation."""
    selected_data = {"id": "pkg-123", "name": "test-package"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_validate_can_generate", return_value=True)
    mock_task_manager = mocker.MagicMock()
    app.generation_task_manager = mock_task_manager
    app.selected_row_index = 5
    app.docset_status_col_grid_idx = 6
    app.on_generate_docset(event=None)
    mock_task_manager.start_generation_task.assert_called_once_with(
        package_data=selected_data,
        row_index=5,
        docset_status_col_idx=6,
    )


def test_on_generate_docset_no_selection(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify it shows a message box if no package is selected."""
    app.selected_row_index = None
    mock_task_manager = mocker.MagicMock()
    app.generation_task_manager = mock_task_manager
    app.on_generate_docset(event=None)
    wx.MessageBox.assert_called_once()
    assert "Please select a package" in wx.MessageBox.call_args[0][0]
    mock_task_manager.start_generation_task.assert_not_called()


def test_on_generate_docset_validation_fails(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify nothing happens if pre-generation validation fails."""
    selected_data = {"id": "pkg-123", "name": "test-package"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_validate_can_generate", return_value=False)
    mock_task_manager = mocker.MagicMock()
    app.generation_task_manager = mock_task_manager
    app.selected_row_index = 0
    app.on_generate_docset(event=None)
    app._validate_can_generate.assert_called_once_with(selected_data)
    mock_task_manager.start_generation_task.assert_not_called()


def test_on_generate_docset_task_manager_not_ready(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify it shows an error if the task manager is not initialized."""
    selected_data = {"id": "pkg-123", "name": "test-package"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_validate_can_generate", return_value=True)
    app.generation_task_manager = None
    app.selected_row_index = 0
    app.on_generate_docset(event=None)
    wx.MessageBox.assert_called_once()
    assert "Generation system not ready" in wx.MessageBox.call_args[0][0]


def test_on_open_docset_success(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify the success path for opening a docset with an index.html."""
    app.selected_row_index = 0
    selected_data = {"name": "test-package", "docset_path": "/fake/path"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mock_docset_path = mocker.MagicMock(spec=Path)
    mock_index_path = mocker.MagicMock(spec=Path)
    mock_index_path.exists.return_value = True
    mock_index_path.is_file.return_value = True
    mock_index_path.as_uri.return_value = "file:///fake/path/index.html"
    mock_docset_path.__truediv__.return_value = mock_index_path
    mocker.patch("devildex.main.Path", return_value=mock_docset_path)
    mocker.patch.object(app, "show_document")
    app.document_view_panel = mocker.MagicMock()
    app.on_open_docset(event=mocker.MagicMock())
    app.show_document.assert_called_once_with(
        package_data_to_show={"name": "test-package"}
    )
    app.document_view_panel.load_url.assert_called_once_with(
        "file:///fake/path/index.html"
    )


def test_on_open_docset_no_selection(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify it shows a message box if no package is selected."""
    app.selected_row_index = None
    mock_show_doc = mocker.patch.object(app, "show_document")
    app.on_open_docset(event=mocker.MagicMock())
    wx.MessageBox.assert_called_once()
    assert "Please select a package" in wx.MessageBox.call_args[0][0]
    mock_show_doc.assert_not_called()


def test_on_open_docset_no_path_in_data(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify it shows a message box if the selected package has no docset_path."""
    app.selected_row_index = 0
    selected_data = {"name": "test-package"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "show_document")
    app.on_open_docset(event=mocker.MagicMock())
    wx.MessageBox.assert_called_once()
    assert "Docset path not found" in wx.MessageBox.call_args[0][0]
    app.show_document.assert_not_called()


def test_on_open_docset_fallback_to_other_html(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify it opens the first available HTML file if index.html is missing."""
    app.selected_row_index = 0
    selected_data = {"name": "test-package", "docset_path": "/fake/path"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mock_docset_path = mocker.MagicMock(spec=Path)
    mock_index_path = mocker.MagicMock(spec=Path)
    mock_index_path.exists.return_value = False
    mock_docset_path.__truediv__.return_value = mock_index_path
    fallback_html_path = mocker.MagicMock(spec=Path)
    fallback_html_path.as_uri.return_value = "file:///fake/path/docs.html"
    mock_docset_path.glob.return_value = [fallback_html_path]

    mocker.patch("devildex.main.Path", return_value=mock_docset_path)

    mocker.patch.object(app, "show_document")
    app.document_view_panel = mocker.MagicMock()
    app.on_open_docset(event=mocker.MagicMock())
    app.document_view_panel.load_url.assert_called_once_with(
        "file:///fake/path/docs.html"
    )


def test_on_open_docset_no_html_files_found(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify it shows an error if no HTML files are found in the docset dir."""
    app.selected_row_index = 0
    selected_data = {"name": "test-package", "docset_path": "/fake/path"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mock_docset_path = mocker.MagicMock(spec=Path)
    mock_index_path = mocker.MagicMock(spec=Path)
    mock_index_path.exists.return_value = False
    mock_docset_path.__truediv__.return_value = mock_index_path
    mock_docset_path.glob.return_value = []
    mocker.patch("devildex.main.Path", return_value=mock_docset_path)
    mocker.patch.object(app, "show_document")
    app.on_open_docset(event=mocker.MagicMock())
    wx.MessageBox.assert_called_once()
    assert (
        "Could not find 'index.html' or any other HTML" in wx.MessageBox.call_args[0][0]
    )
    app.show_document.assert_not_called()


def test_on_view_mode_changed_success(app: DevilDexApp, mocker: MockerFixture) -> None:
    """Verify the full success path for changing the view mode."""
    mock_event = mocker.MagicMock(spec=wx.CommandEvent)
    app.view_mode_selector = mocker.MagicMock()
    app.view_mode_selector.GetValue.return_value = "Project: MyProject"
    mocker.patch.object(app, "_can_process_view_change", return_value=True)
    mock_handle_core = mocker.patch.object(
        app, "_handle_core_project_setting", return_value=True
    )
    mock_bootstrap = app.core.bootstrap_database_and_load_data
    mock_update_ui = mocker.patch.object(app, "_update_ui_after_data_load")
    app.panel = mocker.MagicMock()
    app.on_view_mode_changed(mock_event)
    mock_handle_core.assert_called_once_with("Project: MyProject")
    mock_bootstrap.assert_called_once()
    mock_update_ui.assert_called_once()
    app.panel.Layout.assert_called_once()
    mock_event.Skip.assert_called_once()


def test_on_view_mode_changed_cannot_process(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify it aborts early if _can_process_view_change is False."""
    mock_event = mocker.MagicMock(spec=wx.CommandEvent)
    mocker.patch.object(app, "_can_process_view_change", return_value=False)
    mock_handle_core = mocker.patch.object(app, "_handle_core_project_setting")
    app.on_view_mode_changed(mock_event)
    mock_handle_core.assert_not_called()
    mock_event.Skip.assert_called_once()


def test_on_view_mode_changed_core_setting_fails(
    app: DevilDexApp, mocker: MockerFixture
) -> None:
    """Verify it aborts if setting the project in the core fails."""
    mock_event = mocker.MagicMock(spec=wx.CommandEvent)
    app.view_mode_selector = mocker.MagicMock()
    app.view_mode_selector.GetValue.return_value = "Project: BadProject"
    mocker.patch.object(app, "_can_process_view_change", return_value=True)
    mocker.patch.object(app, "_handle_core_project_setting", return_value=False)
    mock_bootstrap = app.core.bootstrap_database_and_load_data
    app.on_view_mode_changed(mock_event)
    mock_bootstrap.assert_not_called()
    mock_event.Skip.assert_called_once()


@pytest.mark.parametrize(
    "test_case",
    [
        {
            "package_data": {
                "id": "pkg-123",
                "name": "p",
                "docset_status": "Not Available",
            },
            "task_active": False,
            "core_exists": True,
            "expected_result": True,
            "expected_msg_part": None,
        },
        {
            "package_data": {"name": "p", "docset_status": "Not Available"},
            "task_active": False,
            "core_exists": True,
            "expected_result": False,
            "expected_msg_part": "Package ID missing",
        },
        {
            "package_data": {
                "id": "pkg-123",
                "name": "p",
                "docset_status": "Not Available",
            },
            "task_active": True,
            "core_exists": True,
            "expected_result": False,
            "expected_msg_part": "already in progress",
        },
        {
            "package_data": {
                "id": "pkg-123",
                "name": "p",
                "docset_status": AVAILABLE_BTN_LABEL,
            },
            "task_active": False,
            "core_exists": True,
            "expected_result": False,
            "expected_msg_part": "already available",
        },
        {
            "package_data": {
                "id": "pkg-123",
                "name": "p",
                "docset_status": "Not Available",
            },
            "task_active": False,
            "core_exists": False,
            "expected_result": False,
            "expected_msg_part": "Core component non è initialized",
        },
    ],
    ids=[
        "success",
        "no_package_id",
        "task_already_active",
        "docset_already_available",
        "no_core",
    ],
)
def test_validate_can_generate_scenarios(
    app: DevilDexApp,
    mocker: MockerFixture,
    test_case: dict,
) -> None:
    """Verify _validate_can_generate handles various scenarios correctly."""
    package_data = test_case["package_data"]
    task_active = test_case["task_active"]
    core_exists = test_case["core_exists"]
    expected_result = test_case["expected_result"]
    expected_msg_part = test_case["expected_msg_part"]
    if not core_exists:
        app.core = None
    mock_task_manager = mocker.MagicMock()
    mock_task_manager.is_task_active_for_package.return_value = task_active
    app.generation_task_manager = mock_task_manager
    result = app._validate_can_generate(package_data)
    assert result is expected_result
    if expected_msg_part:
        wx.MessageBox.assert_called_once()
        assert expected_msg_part in wx.MessageBox.call_args[0][0]
    else:
        wx.MessageBox.assert_not_called()
