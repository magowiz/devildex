"""Tests for the GenerationTaskManager."""
from unittest.mock import MagicMock

import pytest
import wx
from pytest_mock import MockerFixture

from devildex.task_manager import GenerationTaskManager


@pytest.fixture
def mock_core(mocker: MockerFixture) -> MagicMock:
    """Provide a mock DevilDexCore."""
    core = mocker.MagicMock(name="DevilDexCore")
    core.generate_docset.return_value = (True, "/fake/path/to/docset")
    return core


@pytest.fixture
def mock_owner(mocker: MockerFixture) -> MagicMock:
    """Provide a mock owner window for the timer."""
    owner = mocker.MagicMock(spec=wx.Frame)
    owner.docset_status_col_grid_idx = 5
    return owner


@pytest.fixture
def mock_callbacks(mocker: MockerFixture) -> dict:
    """Provide a dictionary of mock callback functions."""
    return {
        "update_grid": mocker.MagicMock(name="update_grid_cell_callback"),
        "on_complete": mocker.MagicMock(name="on_task_complete_callback"),
        "update_buttons": mocker.MagicMock(name="update_action_buttons_callback"),
    }


@pytest.fixture
def task_manager(
    mock_core, mock_owner, mock_callbacks, mocker: MockerFixture
) -> GenerationTaskManager:
    """Provide an instance of GenerationTaskManager with mocked dependencies."""
    mock_timer_class = mocker.patch("wx.Timer")
    mock_timer_instance = mock_timer_class.return_value
    mock_timer_instance.IsRunning.return_value = False

    mocker.patch("threading.Thread")
    mocker.patch("wx.CallAfter")

    manager = GenerationTaskManager(
        core_instance=mock_core,
        owner_for_timer=mock_owner,
        update_grid_cell_callback=mock_callbacks["update_grid"],
        on_task_complete_callback=mock_callbacks["on_complete"],
        update_action_buttons_callback=mock_callbacks["update_buttons"],
    )
    return manager


# --- Test Cases ---


def test_start_generation_task_success(
    task_manager: GenerationTaskManager, mocker: MockerFixture
) -> None:
    """Verify that a new generation task can be started successfully."""
    # Arrange
    package_data = {"id": "pkg-123", "name": "test-package"}
    row_index = 1
    col_index = 5
    mock_thread_class = mocker.patch("threading.Thread")
    mock_thread_instance = mock_thread_class.return_value

    # Act
    result = task_manager.start_generation_task(package_data, row_index, col_index)

    # Assert
    assert result is True
    assert "pkg-123" in task_manager.active_tasks
    task_manager.animation_timer.Start.assert_called_once_with(150)

    mock_thread_class.assert_called_once_with(
        target=task_manager._perform_generation_in_thread,
        args=(package_data, row_index),
    )
    assert mock_thread_instance.daemon is True
    mock_thread_instance.start.assert_called_once()


def test_start_generation_task_already_active(
    task_manager: GenerationTaskManager, mocker: MockerFixture
) -> None:
    """Verify that a task for the same package cannot be started if one is active."""
    # Arrange
    package_data = {"id": "pkg-123", "name": "test-package"}
    task_manager.active_tasks["pkg-123"] = 1
    mock_thread_class = mocker.patch("threading.Thread")

    # Act
    result = task_manager.start_generation_task(package_data, 1, 5)

    # Assert
    assert result is False
    task_manager.animation_timer.Start.assert_not_called()
    mock_thread_class.assert_not_called()


def test_on_animation_tick_updates_grid_for_active_tasks(
    task_manager: GenerationTaskManager, mock_callbacks: dict, mock_owner
) -> None:
    """Verify the timer callback updates the UI for all active tasks."""
    # Arrange
    task_manager.active_tasks = {"pkg-123": 1, "pkg-456": 3}
    task_manager.current_animation_frame_idx = 0
    update_grid_cb = mock_callbacks["update_grid"]

    # Act
    task_manager._on_animation_tick(None)

    # Assert
    assert task_manager.current_animation_frame_idx == 1
    assert update_grid_cb.call_count == 2
    new_frame_char = task_manager.animation_frames[1]
    update_grid_cb.assert_any_call(
        1, mock_owner.docset_status_col_grid_idx, new_frame_char
    )
    update_grid_cb.assert_any_call(
        3, mock_owner.docset_status_col_grid_idx, new_frame_char
    )


def test_perform_generation_in_thread_handles_success(
    task_manager: GenerationTaskManager, mock_core, mocker: MockerFixture
) -> None:
    """Verify the thread worker calls the core and wx.CallAfter on success."""
    # Arrange
    package_data = {"id": "pkg-123", "name": "test-package"}
    row_index = 1
    mock_call_after = mocker.patch("wx.CallAfter")
    mock_core.generate_docset.return_value = (True, "/fake/path")

    # Act
    task_manager._perform_generation_in_thread(package_data, row_index)

    # Assert
    mock_core.generate_docset.assert_called_once_with(package_data)
    mock_call_after.assert_called_once_with(
        task_manager._handle_task_completion,
        True,
        "/fake/path",
        "test-package",
        "pkg-123",
        row_index,
    )


def test_perform_generation_in_thread_handles_failure(
    task_manager: GenerationTaskManager, mock_core, mocker: MockerFixture
) -> None:
    """Verify the thread worker calls the core and wx.CallAfter on failure."""
    # Arrange
    package_data = {"id": "pkg-123", "name": "test-package"}
    row_index = 1
    mock_call_after = mocker.patch("wx.CallAfter")
    mock_core.generate_docset.return_value = (False, "Explosion!")

    # Act
    task_manager._perform_generation_in_thread(package_data, row_index)

    # Assert
    mock_core.generate_docset.assert_called_once_with(package_data)
    mock_call_after.assert_called_once_with(
        task_manager._handle_task_completion,
        False,
        "Explosion!",
        "test-package",
        "pkg-123",
        row_index,
    )


def test_handle_task_completion_cleans_up_and_notifies(
    task_manager: GenerationTaskManager, mock_callbacks: dict
) -> None:
    """Verify the completion handler cleans up state and calls final callbacks."""
    # Arrange
    task_manager.active_tasks = {"pkg-123": 1}
    on_complete_cb = mock_callbacks["on_complete"]
    update_buttons_cb = mock_callbacks["update_buttons"]
    task_manager.animation_timer.IsRunning.return_value = True

    # Act
    task_manager._handle_task_completion(
        success=True,
        message="/path",
        package_name="test-package",
        package_id="pkg-123",
        row_index=1,
    )

    # Assert
    assert "pkg-123" not in task_manager.active_tasks
    assert not task_manager.active_tasks

    on_complete_cb.assert_called_once_with(True, "/path", "test-package", "pkg-123", 1)
    update_buttons_cb.assert_called_once()
    task_manager.animation_timer.Stop.assert_called_once()
