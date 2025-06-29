"""task manager module."""

import logging
import threading
from typing import Callable, Optional

import wx

from devildex.core import DevilDexCore

logger_task_manager = logging.getLogger(__name__ + ".GenerationTaskManager")


class GenerationTaskManager:
    """Manages background docset generation tasks, UI animation, and callbacks."""

    def __init__(
        self,
        core_instance: "DevilDexCore",
        owner_for_timer: wx.EvtHandler,
        update_grid_cell_callback: Callable[[int, int, str], None],
        on_task_complete_callback: Callable[
            [bool, str, Optional[str], Optional[str], int], None
        ],
        update_action_buttons_callback: Callable[[], None],
    ) -> None:
        """Initialize the GenerationTaskManager.

        Args:
            core_instance: The instance of DevilDexCore.
            owner_for_timer: The wx.EvtHandler owner for the animation timer
                (e.g., the main app frame).
            update_grid_cell_callback: Callback to update a specific grid cell
                (row, col, value).
            on_task_complete_callback: Callback when a generation task finishes.
                                       (success, message, package_name, package_id,
                                       row_index)
            update_action_buttons_callback: Callback to refresh the state of
                action buttons.

        """
        self.core = core_instance
        self.owner_for_timer = owner_for_timer
        self.update_grid_cell_callback = update_grid_cell_callback
        self.on_task_complete_callback = on_task_complete_callback
        self.update_action_buttons_callback = update_action_buttons_callback

        self.active_tasks: dict[str, int] = {}  # package_id -> row_index
        self.animation_frames: list[str] = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
        self.current_animation_frame_idx: int = 0
        self.animation_timer: wx.Timer = wx.Timer(owner_for_timer)
        self.owner_for_timer.Bind(
            wx.EVT_TIMER, self._on_animation_tick, self.animation_timer
        )

    def is_task_active_for_package(self, package_id: str) -> bool:
        """Check if a task for the given package_id is currently active."""
        return package_id in self.active_tasks

    def has_any_active_tasks(self) -> bool:
        """Check if there are any active generation tasks."""
        return bool(self.active_tasks)

    def start_generation_task(
        self, package_data: dict, row_index: int, docset_status_col_idx: int
    ) -> bool:
        """Initiate a docset generation task.

        Args:
            package_data: Dictionary containing package details
                (must include 'id', 'name').
            row_index: The grid row index for this package.
            docset_status_col_idx: The column index in the grid for docset status.

        Returns:
            True if the task was started, False otherwise (e.g., task already active).

        """
        package_id = package_data.get("id")
        package_name = package_data.get("name", "N/D")

        if not package_id:
            logger_task_manager.error("Cannot start generation: package_id is missing.")
            # Consider a way to notify UI, or let DevilDexApp handle this pre-check
            return False

        if self.is_task_active_for_package(package_id):
            logger_task_manager.info(
                f"Generation for '{package_name}' is already in progress."
            )
            return False

        logger_task_manager.info(
            f"Starting generation task for '{package_name}' (ID: {package_id})"
            f" at row {row_index}."
        )
        self.active_tasks[package_id] = row_index
        self.update_action_buttons_callback()  # Update buttons immediately

        # Initial animation frame
        if docset_status_col_idx != -1:
            first_animation_frame = self.animation_frames[0]
            self.update_grid_cell_callback(
                row_index, docset_status_col_idx, first_animation_frame
            )
            # DevilDexApp will also need to update its current_grid_source_data

        if not self.animation_timer.IsRunning():
            self.animation_timer.Start(150)
            logger_task_manager.debug("Animation timer started.")

        # Prepare data for the thread to avoid issues with shared wx objects if any
        thread_package_data = package_data.copy()
        worker = threading.Thread(
            target=self._perform_generation_in_thread,
            args=(thread_package_data, row_index),  # Pass row_index for the callback
        )
        worker.daemon = True
        worker.start()
        return True

    def _perform_generation_in_thread(self, package_data: dict, row_index: int) -> None:
        """Execute the docset generation in a separate thread.

        Calls core and sends the result to the GUI using wx.CallAfter.
        """
        package_name_for_msg = package_data.get("name", "N/D")
        package_id_for_completion = package_data.get("id")

        if not package_id_for_completion:  # Should have been caught earlier
            logger_task_manager.error(
                "Thread: package_id missing, aborting generation."
            )
            return

        try:
            if not self.core:
                error_message = "Error in thread: Core instance not available."
                logger_task_manager.error(error_message)
                wx.CallAfter(
                    self._handle_task_completion,
                    False,
                    error_message,
                    package_name_for_msg,
                    package_id_for_completion,
                    row_index,
                )
                return

            logger_task_manager.info(
                f"Thread: Calling core.generate_docset for {package_name_for_msg}"
            )
            success, message = self.core.generate_docset(package_data)
            logger_task_manager.info(
                f"Thread: core.generate_docset for {package_name_for_msg}"
                f" completed. Success: {success}"
            )
            wx.CallAfter(
                self._handle_task_completion,
                success,
                message,
                package_name_for_msg,
                package_id_for_completion,
                row_index,
            )

        except Exception as e:
            error_message = (
                f"Unexpected Exception during generation for "
                f"'{package_name_for_msg}' in thread: {e}"
            )
            logger_task_manager.exception(error_message)  # Log with traceback
            wx.CallAfter(
                self._handle_task_completion,
                False,
                error_message,
                package_name_for_msg,
                package_id_for_completion,
                row_index,
            )

    def _handle_task_completion(
        self,
        success: bool,
        message: str,
        package_name: Optional[str],
        package_id: Optional[str],
        row_index: int,  # The original row index for this task
    ) -> None:
        """Handle the completion of a generation task.

        This method is executed in the main GUI thread using wx.CallAfter.
        """
        if not package_id:
            logger_task_manager.warning("Task completion handled with no package_id.")
            self._stop_animation_timer_if_no_tasks()
            self.update_action_buttons_callback()
            return

        original_row_idx_of_task = self.active_tasks.pop(package_id, -1)

        if original_row_idx_of_task == -1:
            logger_task_manager.warning(
                f"Task for package_id '{package_id}' was not "
                "found in active_tasks upon completion."
            )

        self._stop_animation_timer_if_no_tasks()
        self.on_task_complete_callback(
            success, message, package_name, package_id, row_index
        )
        self.update_action_buttons_callback()

    def _on_animation_tick(self, event: wx.TimerEvent) -> None:
        """Update animation frames for rows currently in generation."""
        if not self.active_tasks:
            if event:
                event.Skip()
            return

        self.current_animation_frame_idx = (self.current_animation_frame_idx + 1) % len(
            self.animation_frames
        )
        current_frame_char = self.animation_frames[self.current_animation_frame_idx]

        # Assuming DevilDexApp knows the docset_status_col_grid_idx
        # This might need to be passed or stored if it can change
        docset_status_col_idx = -1  # Placeholder, DevilDexApp will know this
        if hasattr(self.owner_for_timer, "docset_status_col_grid_idx"):
            docset_status_col_idx = self.owner_for_timer.docset_status_col_grid_idx

        if docset_status_col_idx != -1:
            for _, row_idx in list(self.active_tasks.items()):
                self.update_grid_cell_callback(
                    row_idx, docset_status_col_idx, current_frame_char
                )
        if event:
            event.Skip()

    def _stop_animation_timer_if_no_tasks(self) -> None:
        """Stop the animation timer if no generation tasks are active."""
        if (
            self.animation_timer
            and not self.active_tasks
            and self.animation_timer.IsRunning()
        ):
            self.animation_timer.Stop()
            self.current_animation_frame_idx = 0
            logger_task_manager.debug(
                "No remaining active tasks, animation timer stopped."
            )

    def cleanup(self) -> None:
        """Clean up resources, like stopping the timer."""
        if self.animation_timer and self.animation_timer.IsRunning():
            self.animation_timer.Stop()
        logger_task_manager.debug("GenerationTaskManager cleaned up.")
