"""Tests for the business logic within the DevilDexApp class.

These tests focus on the application's logic, mocking UI components
and core functionalities to ensure methods behave as expected without
a running GUI.
"""

from pathlib import Path

import pytest
import wx
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

    # Attach mocks for UI collaborators
    app_instance.actions_panel = mocker.MagicMock(name="ActionsPanel")
    # Mock MessageBox to prevent dialogs from popping up during tests
    mocker.patch("wx.MessageBox")

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


# --- Tests for on_delete_docset ---


def test_on_delete_docset_success(app: DevilDexApp, mocker: MockerFixture):
    """Verify the full success path for deleting a docset."""
    # Arrange
    selected_data = {"name": "test-package", "docset_path": "/fake/path/docset"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_confirm_deletion", return_value=True)
    app.core.delete_docset_build.return_value = (True, "Success")

    mock_handle_success = mocker.patch.object(app, "_handle_delete_success")
    mock_update_buttons = mocker.patch.object(app, "_update_action_buttons_state")

    # Act
    app.on_delete_docset(event=None)

    # Assert
    app.core.delete_docset_build.assert_called_once_with("/fake/path/docset")
    mock_handle_success.assert_called_once_with("test-package")
    mock_update_buttons.assert_called_once()


def test_on_delete_docset_user_cancels(app: DevilDexApp, mocker: MockerFixture):
    """Verify nothing happens if the user cancels the deletion."""
    # Arrange
    selected_data = {"name": "test-package", "docset_path": "/fake/path/docset"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_confirm_deletion", return_value=False)  # User says NO

    # Act
    app.on_delete_docset(event=None)

    # Assert
    # The core deletion method should NOT be called
    app.core.delete_docset_build.assert_not_called()


def test_on_delete_docset_core_fails(app: DevilDexApp, mocker: MockerFixture):
    """Verify the failure path is handled when the core cannot delete."""
    # Arrange
    selected_data = {"name": "test-package", "docset_path": "/fake/path/docset"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_confirm_deletion", return_value=True)
    app.core.delete_docset_build.return_value = (False, "Permission denied")

    mock_handle_failure = mocker.patch.object(app, "_handle_delete_failure")
    mock_update_buttons = mocker.patch.object(app, "_update_action_buttons_state")

    # Act
    app.on_delete_docset(event=None)

    # Assert
    app.core.delete_docset_build.assert_called_once_with("/fake/path/docset")
    mock_handle_failure.assert_called_once_with("test-package", "Permission denied")
    mock_update_buttons.assert_called_once()


def test_on_delete_docset_no_path_in_data(app: DevilDexApp, mocker: MockerFixture):
    """Verify it shows a message box if the selected package has no path."""
    # Arrange
    selected_data = {"name": "test-package"}  # No 'docset_path'
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)

    # Act
    app.on_delete_docset(event=None)

    # Assert
    wx.MessageBox.assert_called_once()
    assert "No docset path found" in wx.MessageBox.call_args[0][0]
    app.core.delete_docset_build.assert_not_called()


# --- Tests for on_generate_docset ---


def test_on_generate_docset_success(app: DevilDexApp, mocker: MockerFixture):
    """Verify the success path for starting a docset generation."""
    # Arrange
    selected_data = {"id": "pkg-123", "name": "test-package"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_validate_can_generate", return_value=True)

    # Mock the task manager and its dependencies
    mock_task_manager = mocker.MagicMock()
    app.generation_task_manager = mock_task_manager
    app.selected_row_index = 5
    app.docset_status_col_grid_idx = 6  # Example column index

    # Act
    app.on_generate_docset(event=None)

    # Assert
    mock_task_manager.start_generation_task.assert_called_once_with(
        package_data=selected_data,
        row_index=5,
        docset_status_col_idx=6,
    )


def test_on_generate_docset_no_selection(app: DevilDexApp, mocker: MockerFixture):
    """Verify it shows a message box if no package is selected."""
    # Arrange
    app.selected_row_index = None  # Explicitly set no selection
    mock_task_manager = mocker.MagicMock()
    app.generation_task_manager = mock_task_manager

    # Act
    app.on_generate_docset(event=None)

    # Assert
    wx.MessageBox.assert_called_once()
    assert "Please select a package" in wx.MessageBox.call_args[0][0]
    mock_task_manager.start_generation_task.assert_not_called()


def test_on_generate_docset_validation_fails(app: DevilDexApp, mocker: MockerFixture):
    """Verify nothing happens if pre-generation validation fails."""
    # Arrange
    selected_data = {"id": "pkg-123", "name": "test-package"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    # Simulate validation failure (the method itself is responsible for the message box)
    mocker.patch.object(app, "_validate_can_generate", return_value=False)
    mock_task_manager = mocker.MagicMock()
    app.generation_task_manager = mock_task_manager
    app.selected_row_index = 0  # FIX: Simulate a row is selected

    # Act
    app.on_generate_docset(event=None)

    # Assert
    # The validation method is called, but the task manager is not.
    app._validate_can_generate.assert_called_once_with(selected_data)
    mock_task_manager.start_generation_task.assert_not_called()


def test_on_generate_docset_task_manager_not_ready(
    app: DevilDexApp, mocker: MockerFixture
):
    """Verify it shows an error if the task manager is not initialized."""
    # Arrange
    selected_data = {"id": "pkg-123", "name": "test-package"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "_validate_can_generate", return_value=True)
    app.generation_task_manager = None  # Simulate it not being ready
    app.selected_row_index = 0  # FIX: Simulate a row is selected

    # Act
    app.on_generate_docset(event=None)

    # Assert
    wx.MessageBox.assert_called_once()
    assert "Generation system not ready" in wx.MessageBox.call_args[0][0]


# --- Tests for on_open_docset ---


def test_on_open_docset_success(app: DevilDexApp, mocker: MockerFixture):
    """Verify the success path for opening a docset with an index.html."""
    # Arrange
    app.selected_row_index = 0
    selected_data = {"name": "test-package", "docset_path": "/fake/path"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)

    # Mock Path objects robustly
    mock_docset_path = mocker.MagicMock(spec=Path)
    mock_index_path = mocker.MagicMock(spec=Path)
    mock_index_path.exists.return_value = True
    mock_index_path.is_file.return_value = True
    mock_index_path.as_uri.return_value = "file:///fake/path/index.html"
    mock_docset_path.__truediv__.return_value = mock_index_path
    mocker.patch("devildex.main.Path", return_value=mock_docset_path)

    # Mock the UI methods that get called
    mocker.patch.object(app, "show_document")
    app.document_view_panel = mocker.MagicMock()

    # Act
    app.on_open_docset(event=mocker.MagicMock())

    # Assert
    app.show_document.assert_called_once_with(
        package_data_to_show={"name": "test-package"}
    )
    app.document_view_panel.load_url.assert_called_once_with(
        "file:///fake/path/index.html"
    )


def test_on_open_docset_no_selection(app: DevilDexApp, mocker: MockerFixture):
    """Verify it shows a message box if no package is selected."""
    # Arrange
    app.selected_row_index = None
    mock_show_doc = mocker.patch.object(app, "show_document")

    # Act
    app.on_open_docset(event=mocker.MagicMock())

    # Assert
    wx.MessageBox.assert_called_once()
    assert "Please select a package" in wx.MessageBox.call_args[0][0]
    mock_show_doc.assert_not_called()


def test_on_open_docset_no_path_in_data(app: DevilDexApp, mocker: MockerFixture):
    """Verify it shows a message box if the selected package has no docset_path."""
    # Arrange
    app.selected_row_index = 0
    selected_data = {"name": "test-package"}  # No 'docset_path'
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)
    mocker.patch.object(app, "show_document")

    # Act
    app.on_open_docset(event=mocker.MagicMock())

    # Assert
    wx.MessageBox.assert_called_once()
    assert "Docset path not found" in wx.MessageBox.call_args[0][0]
    app.show_document.assert_not_called()


def test_on_open_docset_fallback_to_other_html(app: DevilDexApp, mocker: MockerFixture):
    """Verify it opens the first available HTML file if index.html is missing."""
    # Arrange
    app.selected_row_index = 0
    selected_data = {"name": "test-package", "docset_path": "/fake/path"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)

    # Mock Path objects robustly
    mock_docset_path = mocker.MagicMock(spec=Path)
    mock_index_path = mocker.MagicMock(spec=Path)
    mock_index_path.exists.return_value = False  # index.html does NOT exist
    mock_docset_path.__truediv__.return_value = mock_index_path

    # Mock the glob call to find a fallback
    fallback_html_path = mocker.MagicMock(spec=Path)
    fallback_html_path.as_uri.return_value = "file:///fake/path/docs.html"
    mock_docset_path.glob.return_value = [fallback_html_path]

    mocker.patch("devildex.main.Path", return_value=mock_docset_path)

    mocker.patch.object(app, "show_document")
    app.document_view_panel = mocker.MagicMock()

    # Act
    app.on_open_docset(event=mocker.MagicMock())

    # Assert
    app.document_view_panel.load_url.assert_called_once_with(
        "file:///fake/path/docs.html"
    )


def test_on_open_docset_no_html_files_found(app: DevilDexApp, mocker: MockerFixture):
    """Verify it shows an error if no HTML files are found in the docset dir."""
    # Arrange
    app.selected_row_index = 0
    selected_data = {"name": "test-package", "docset_path": "/fake/path"}
    mocker.patch.object(app, "get_selected_row", return_value=selected_data)

    # Mock Path objects robustly
    mock_docset_path = mocker.MagicMock(spec=Path)
    mock_index_path = mocker.MagicMock(spec=Path)
    mock_index_path.exists.return_value = False  # index.html does NOT exist
    mock_docset_path.__truediv__.return_value = mock_index_path
    mock_docset_path.glob.return_value = []  # No fallback files either
    mocker.patch("devildex.main.Path", return_value=mock_docset_path)

    mocker.patch.object(app, "show_document")

    # Act
    app.on_open_docset(event=mocker.MagicMock())

    # Assert
    wx.MessageBox.assert_called_once()
    assert (
        "Could not find 'index.html' or any other HTML" in wx.MessageBox.call_args[0][0]
    )
    app.show_document.assert_not_called()
