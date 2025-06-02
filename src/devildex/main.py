"""main application."""
import logging
import shutil
import threading
from pathlib import Path
from typing import Any, ClassVar, Optional

import wx
import wx.grid
import wx.html2

from devildex.models import PackageDetails
from devildex.orchestrator.documentation_orchestrator import Orchestrator
from examples.sample_data import COLUMNS_ORDER, PACKAGES_DATA

logger = logging.getLogger(__name__)
COL_WIDTH_ID = 160
COL_WIDTH_NAME = 160
COL_WIDTH_VERSION = 80
COL_WIDTH_DESC = 200
COL_WIDTH_STATUS = 120
COL_WIDTH_DOCSET_STATUS = 140


class DevilDexCore:
    """DevilDex Core."""

    def __init__(self) -> None:
        """Initialize a new DevilDexCore instance."""
        self.docset_base_output_path = Path("devildex_docsets")
        self.docset_base_output_path.mkdir(parents=True, exist_ok=True)



    def list_package_dirs(self) -> list[str]:
        """List i nomi delle directory di primo level nella folder base dei docset.

        These are potential folders root per i packages.
        """
        if not self.docset_base_output_path.exists():
            return []
        return [d.name for d in self.docset_base_output_path.iterdir() if d.is_dir()]
    def generate_docset(self, package_data: dict) -> tuple[bool, str]:
        """Generate a docset using Orchestrator.

        Returns (success, message).
        """
        package_name = package_data.get("name")
        package_version = package_data.get("version")
        project_urls = package_data.get("project_urls")
        if not package_name or not package_version:
            error_msg = "missing package name or version nei dati di input."
            return False, error_msg
        details = PackageDetails(
            name=str(package_name),
            version=str(package_version),
            project_urls=project_urls if isinstance(project_urls, dict) else {},
        )
        orchestrator = Orchestrator(
            package_details=details,
            base_output_dir=self.docset_base_output_path,
        )
        orchestrator.start_scan()
        detected_type = orchestrator.get_detected_doc_type()
        if detected_type == "unknown":
            last_op_msg = orchestrator.get_last_operation_result()
            msg = (
                f"unable to determine il tipo di documentation per {details.name}."
            )
            if isinstance(last_op_msg, str) and last_op_msg:
                msg += f" Detail: {last_op_msg}"
            return False, msg
        generation_result = orchestrator.grab_build_doc()
        if isinstance(generation_result, str):
            return True, generation_result
        elif generation_result is False:
            last_op_detail = orchestrator.get_last_operation_result()
            error_msg = f"Failure nella generation del docset per {details.name}."
            if isinstance(last_op_detail, str) and last_op_detail:
                error_msg += f" Details: {last_op_detail}"
            elif last_op_detail is False:
                error_msg += " Specified operation is failed."
            return False, error_msg
        else:
            unexpected_msg = (
                f"Unexpected result ({type(generation_result)}) "
                f"dalla generation del docset per {details.name}."
            )
            return False, unexpected_msg

class DevilDexApp(wx.App):
    """Main Application."""

    def __init__(
        self, core: DevilDexCore | None = None, initial_url: str | None = None
    ) -> None:
        """Initialize a new DevilDexApp instance."""
        self.core = core
        self.home_url = "https://www.google.com"
        self.initial_url = initial_url
        self.main_frame: Optional[wx.Frame] = None
        self.webview: Optional[wx.html2.WebView] = None
        self.back_button: Optional[wx.Button] = None
        self.forward_button: Optional[wx.Button] = None
        self.home_button: Optional[wx.Button] = None
        self.panel: Optional[wx.Panel] = None
        self.main_panel_sizer: Optional[wx.BoxSizer] = None
        self.data_grid: wx.grid.Grid | None = None

        self.current_grid_source_data: list[dict[str, Any]] = []
        for item in PACKAGES_DATA:
            new_item = item.copy()
            if "docset_status" not in new_item:
                new_item["docset_status"] = "Not Available"
            if (
                new_item.get("docset_status") != "📖 Available"
                and "docset_path" in new_item
            ):
                del new_item["docset_path"]
            self.current_grid_source_data.append(new_item)

        self.open_action_button: wx.Button | None = None
        self.generate_action_button: wx.Button | None = None
        self.regenerate_action_button: wx.Button | None = None
        self.view_log_action_button: wx.Button | None = None
        self.delete_action_button: wx.Button | None = None
        self.selected_row_index: int | None = None
        self.custom_highlighted_row_index: Optional[int] = None
        self.custom_row_highlight_attr: Optional[wx.grid.GridCellAttr] = None
        self.indicator_col_idx = 0
        self.log_text_ctrl: Optional[wx.TextCtrl] = None
        self.is_log_panel_visible: bool = False
        self.log_toggle_button: Optional[wx.Button] = None
        self.arrow_up_bmp: Optional[wx.Bitmap] = None
        self.arrow_down_bmp: Optional[wx.Bitmap] = None
        self.is_task_running: bool = False
        self.docset_status_col_grid_idx: int = -1
        self.animation_timer: Optional[wx.Timer] = None
        self.animation_frames: list[str] = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
        self.current_animation_frame_idx: int = 0
        self.active_generation_tasks: dict[str, int] = {}
        self.package_display_label: Optional[wx.StaticText] = None
        self.arrow_up_bmp_scaled: Optional[wx.Bitmap] = None
        self.arrow_down_bmp_scaled: Optional[wx.Bitmap] = None

        super().__init__(redirect=False)
        self.MainLoop()


    def scan_docset_dir(self, grid_pkg: list[dict]) -> set:
        """Scan Docset directory."""
        available_pkg = set()
        pkg_list = self.core.list_package_dirs()
        for pkg in pkg_list:
            for g_pkg in grid_pkg:
                if self.matching_docset(pkg, g_pkg):
                    available_pkg.add(pkg)
                    break
        return available_pkg

    @staticmethod
    def matching_docset(pkg: str, grid_pkg: dict) -> bool:
        """Check if a package name is matching a package in grid."""
        return pkg == grid_pkg.get('name')

    def _perform_startup_docset_scan(self) -> None:
        """Execute the scan dei existing docsets on startup e updates.

        self.current_grid_source_data.
        """
        matched_top_level_dir_names: set[str] = self.scan_docset_dir(
            self.current_grid_source_data
        )
        updated_count = 0
        for pkg_data in self.current_grid_source_data:
            pkg_name = pkg_data.get("name")
            pkg_version = pkg_data.get("version")
            if pkg_name in matched_top_level_dir_names:
                package_root_on_disk: Path = (
                    self.core.docset_base_output_path / pkg_name
                )
                subdirs_to_check = []
                if pkg_version:
                    subdirs_to_check.append(str(pkg_version))
                subdirs_to_check.extend(["main", "master"])
                found_specific_docset_subdir: Optional[Path] = None
                for subdir_candidate_name in subdirs_to_check:
                    potential_docset_path = (
                        package_root_on_disk / subdir_candidate_name
                    )
                    if (
                        potential_docset_path.exists()
                        and potential_docset_path.is_dir()
                    ):
                        found_specific_docset_subdir = potential_docset_path
                        break

                if found_specific_docset_subdir:
                    pkg_data["docset_status"] = "📖 Available"
                    pkg_data["docset_path"] = str(
                        found_specific_docset_subdir.resolve()
                    )
                    updated_count += 1
                else:
                    pkg_data["docset_status"] = "Not Available"
                    if "docset_path" in pkg_data:
                        del pkg_data["docset_path"]
            else:
                pkg_data["docset_status"] = "Not Available"
                if "docset_path" in pkg_data:
                    del pkg_data["docset_path"]


    def show_document(
        self,
        event: wx.CommandEvent | None = None,
        package_data_to_show: Optional[dict] = None,
    ) -> None:
        """Show the document view."""
        if event:
            event.Skip()
        self._clear_main_panel()
        self.package_display_label = wx.StaticText(
            self.panel, label="Loading document..."
        )
        font = self.package_display_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.package_display_label.SetFont(font)
        self.main_panel_sizer.Add(
            self.package_display_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5
        )

        button_sizer = self._setup_navigation_panel(self.panel)
        self.main_panel_sizer.Add(
            button_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5
        )
        self.webview = wx.html2.WebView.New(self.panel)
        self.main_panel_sizer.Add(self.webview, 1, wx.EXPAND | wx.ALL, 5)
        self.update_navigation_buttons_state()
        self.webview.Bind(wx.html2.EVT_WEBVIEW_NAVIGATED, self.on_webview_navigated)
        new_label_text = "Viewing documentation"
        if package_data_to_show:
            package_name = package_data_to_show.get("name", "Unknown Package")
            new_label_text = package_name
        self.package_display_label.SetLabel(new_label_text)
        if self.initial_url:
            self.load_url(self.initial_url)
        self.panel.Layout()

    def OnInit(self) -> bool:  # noqa: N802
        """Set up gui widgets on application startup."""
        wx.Log.SetActiveTarget(wx.LogStderr())
        window_title = "DevilDex"
        self.main_frame = wx.Frame(parent=None, title=window_title, size=(1280, 900))
        self.panel = wx.Panel(self.main_frame)
        self.main_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.main_panel_sizer)
        self.main_frame.Centre()
        self.SetTopWindow(self.main_frame)
        self.custom_row_highlight_attr = wx.grid.GridCellAttr()
        self.custom_row_highlight_attr.SetBackgroundColour(wx.Colour(255, 165, 0))
        self.custom_row_highlight_attr.SetTextColour(wx.BLACK)
        original_icon_size = (16, 16)
        scaled_icon_height = 8
        scaled_icon_width = scaled_icon_height
        scaled_icon_target_size = (scaled_icon_width, scaled_icon_height)

        self.arrow_down_bmp = wx.ArtProvider.GetBitmap(
            wx.ART_GO_DOWN, wx.ART_BUTTON, original_icon_size
        )
        self.arrow_up_bmp = wx.ArtProvider.GetBitmap(
            wx.ART_GO_UP, wx.ART_BUTTON, original_icon_size
        )
        art_down_bitmap = wx.ArtProvider.GetBitmap(
            wx.ART_GO_DOWN, wx.ART_OTHER, original_icon_size
        )

        if art_down_bitmap.IsOk():
            img_down = art_down_bitmap.ConvertToImage()
            if img_down.IsOk():
                img_down.Rescale(
                    scaled_icon_target_size[0],
                    scaled_icon_target_size[1],
                    wx.IMAGE_QUALITY_HIGH,
                )
                self.arrow_down_bmp_scaled = wx.Bitmap(img_down)
            else:
                self.arrow_down_bmp_scaled = None
        else:
            self.arrow_down_bmp_scaled = None
        self._perform_startup_docset_scan()
        art_up_bitmap = wx.ArtProvider.GetBitmap(
            wx.ART_GO_UP, wx.ART_OTHER, original_icon_size
        )
        if art_up_bitmap.IsOk():
            img_up = art_up_bitmap.ConvertToImage()
            if img_up.IsOk():
                img_up.Rescale(
                    scaled_icon_target_size[0],
                    scaled_icon_target_size[1],
                    wx.IMAGE_QUALITY_HIGH,
                )
                self.arrow_up_bmp_scaled = wx.Bitmap(img_up)
            else:
                self.arrow_up_bmp_scaled = None
        else:
            self.arrow_up_bmp_scaled = None
        self.docset_status_col_grid_idx = COLUMNS_ORDER.index("docset_status") + 1
        self.animation_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_animation_tick, self.animation_timer)
        self._setup_initial_view()
        self.main_frame.Show(True)
        return True

    def _set_button_states_for_selected_row(
        self, package_data: dict, action_buttons: dict
    ) -> None:
        """Help to set states for action buttons based on selected package data."""
        selected_package_id = package_data.get("id")
        current_docset_status = package_data.get("docset_status", "Not Available")
        is_generating_this_row = selected_package_id in self.active_generation_tasks

        open_btn = action_buttons.get("open")
        if open_btn:
            can_open = (
                current_docset_status == "📖 Available" and not is_generating_this_row
            )
            open_btn.Enable(can_open)

        generate_btn = action_buttons.get("generate")
        if generate_btn:
            can_generate = (
                not is_generating_this_row
                and current_docset_status != "📖 Available"
                and current_docset_status not in self.animation_frames
            )
            generate_btn.Enable(can_generate)

        regenerate_btn = action_buttons.get("regenerate")
        if regenerate_btn:
            can_regenerate = not is_generating_this_row and current_docset_status in [
                "📖 Available",
                "❌ Error",
            ]
            regenerate_btn.Enable(can_regenerate)

        log_btn = action_buttons.get("log")
        if log_btn:
            log_btn.Enable(True)

        delete_btn = action_buttons.get("delete")
        if delete_btn:
            can_delete = not is_generating_this_row and current_docset_status in [
                "📖 Available",
                "❌ Error",
            ]
            delete_btn.Enable(can_delete)

    def _on_animation_tick(self, event: wx.TimerEvent) -> None:
        """Update frames of animation per le rows in generation."""
        if not self.data_grid or not self.active_generation_tasks:
            if event:
                event.Skip()
            return
        self.current_animation_frame_idx = (self.current_animation_frame_idx + 1) % len(
            self.animation_frames
        )
        current_frame_char = self.animation_frames[self.current_animation_frame_idx]

        for _, row_idx in list(self.active_generation_tasks.items()):
            if (
                0 <= row_idx < self.data_grid.GetNumberRows()
                and self.docset_status_col_grid_idx != -1
            ):
                self.data_grid.SetCellValue(
                    row_idx, self.docset_status_col_grid_idx, current_frame_char
                )
        if event:
            event.Skip()

    def go_home(self, event: wx.CommandEvent | None = None) -> None:
        """Go to initial view."""
        if event:
            event.Skip()
        self._setup_initial_view()

    COL_WIDTHS: ClassVar[dict[str, int]] = {
        "id": COL_WIDTH_ID,
        "name": COL_WIDTH_NAME,
        "version": COL_WIDTH_VERSION,
        "description": COL_WIDTH_DESC,
        "status": COL_WIDTH_STATUS,
        "docset_status": COL_WIDTH_DOCSET_STATUS,
    }

    def _configure_grid_columns(self) -> None:
        """Configura le labels, sizes and attributes delle columns della grid."""
        if not self.data_grid:
            return

        self.data_grid.SetColLabelValue(self.indicator_col_idx, "")
        self.data_grid.SetColSize(
            self.indicator_col_idx, 30
        )
        indicator_attr = wx.grid.GridCellAttr()
        indicator_attr.SetAlignment(wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
        indicator_attr.SetReadOnly(True)
        self.data_grid.SetColAttr(self.indicator_col_idx, indicator_attr.Clone())
        for c_idx, col_name in enumerate(COLUMNS_ORDER):
            grid_col_idx = (
                c_idx + 1
            )
            self.data_grid.SetColLabelValue(grid_col_idx, col_name)
            if col_name in self.COL_WIDTHS:
                self.data_grid.SetColSize(grid_col_idx, self.COL_WIDTHS[col_name])
            col_attr = wx.grid.GridCellAttr()
            col_attr.SetReadOnly(True)
            self.data_grid.SetColAttr(grid_col_idx, col_attr.Clone())

    def _setup_initial_view(self) -> None:
        """Configura la initial window."""
        self._clear_main_panel()
        self.is_log_panel_visible = False

        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.data_grid = wx.grid.Grid(self.panel)
        self.data_grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.on_grid_cell_click)
        content_sizer.Add(self.data_grid, 1, wx.EXPAND | wx.ALL, 5)

        action_buttons_sizer = self._setup_action_buttons_panel(self.panel)
        content_sizer.Add(action_buttons_sizer, 0, wx.EXPAND | wx.ALL, 5)
        num_data_cols = len(COLUMNS_ORDER)
        total_grid_cols = num_data_cols + 1

        self.data_grid.CreateGrid(0, total_grid_cols)
        self.data_grid.SetSelectionMode(wx.grid.Grid.SelectRows)
        self._configure_grid_columns()
        self.log_text_ctrl = wx.TextCtrl(
            self.panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.TE_RICH2,
        )
        self.log_text_ctrl.SetMinSize(wx.Size(-1, 100))
        initial_bmp_to_use = wx.NullBitmap
        if self.arrow_down_bmp_scaled and self.arrow_down_bmp_scaled.IsOk():
            initial_bmp_to_use = self.arrow_down_bmp_scaled
        elif self.arrow_down_bmp and self.arrow_down_bmp.IsOk():
            initial_bmp_to_use = self.arrow_down_bmp
        button_fixed_size = wx.Size(50, 20)
        self.log_toggle_button = wx.BitmapButton(
            self.panel,
            id=wx.ID_ANY,
            bitmap=initial_bmp_to_use,
            size=button_fixed_size,
            style=wx.BU_EXACTFIT,
        )
        self.log_toggle_button.Bind(wx.EVT_BUTTON, self.on_log_toggle_button_click)
        bottom_bar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bottom_bar_sizer.AddStretchSpacer(1)
        button_padding = 0
        bottom_bar_sizer.Add(
            self.log_toggle_button,
            proportion=0,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=button_padding,
        )
        sizer_internal_vertical_padding = 0
        desired_bar_height = (
            button_fixed_size.GetHeight() + sizer_internal_vertical_padding
        )
        bottom_bar_sizer.SetMinSize(wx.Size(-1, desired_bar_height))
        bottom_bar_sizer.AddStretchSpacer(1)
        self.main_panel_sizer.Add(content_sizer, 1, wx.EXPAND | wx.ALL, 0)
        self.main_panel_sizer.Add(self.log_text_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        self.log_text_ctrl.Show(self.is_log_panel_visible)
        self.main_panel_sizer.Add(bottom_bar_sizer, 0, wx.EXPAND | wx.ALL, 0)
        self.update_grid()
        self._update_log_toggle_button_icon()
        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()

    def _set_log_panel_visibility(self, visible: bool) -> None:
        if not self.log_text_ctrl or not self.panel:
            return

        self.is_log_panel_visible = visible
        self.log_text_ctrl.Show(self.is_log_panel_visible)

        item = self.main_panel_sizer.GetItem(self.log_text_ctrl)
        if item:
            item.Show(self.is_log_panel_visible)

        self.panel.Layout()
        self._update_log_toggle_button_icon()



    def on_open_docset(self, event: wx.CommandEvent) -> None:
        """Handle open docset action."""
        if self.selected_row_index is None:
            wx.MessageBox(
                "Please select a package from the grid to open its docset.",
                "No Selection",
                wx.OK | wx.ICON_INFORMATION,
            )
            event.Skip()
            return

        selected_package_data = self.get_selected_row()

        if not selected_package_data:
            wx.MessageBox(
                "Could not retrieve data for the selected row.",
                "Internal Error",
                wx.OK | wx.ICON_ERROR,
            )
            event.Skip()
            return

        docset_path_str = selected_package_data.get("docset_path")
        package_name_for_display = selected_package_data.get(
            "name", "Selected Package"
        )

        if not docset_path_str:
            wx.MessageBox(
                f"Docset path not found for '{package_name_for_display}'.\n"
                "Please generate the docset first.",
                "Docset Not Available",
                wx.OK | wx.ICON_INFORMATION,
            )
            event.Skip()
            return

        docset_path = Path(docset_path_str)
        index_file_path = docset_path / "index.html"

        if not index_file_path.exists() or not index_file_path.is_file():
            html_files = list(docset_path.glob("*.html"))
            if html_files:
                index_file_path = html_files[0]
                logger.error(
                    f"GUI: 'index.html' not found in {docset_path}, using"
                    f"'{index_file_path.name}' as fallback."
                )
            else:
                wx.MessageBox(
                    "Could not find 'index.html' or any other HTML "
                    f"file in the docset directory for '{package_name_for_display}'.\n"
                    f"Path checked: {docset_path}",
                    "Docset Entry Point Error",
                    wx.OK | wx.ICON_ERROR,
                )
                event.Skip()
                return

        package_data_for_view = {
            "name": package_name_for_display,
        }

        self.show_document(package_data_to_show=package_data_for_view)
        if self.webview:
            local_url = index_file_path.as_uri()
            self.load_url(local_url)
        else:
            wx.MessageBox(
                "WebView component is not available. Cannot open docset.",
                "Internal Error",
                wx.OK | wx.ICON_ERROR,
            )

        event.Skip()


    def on_generate_docset(self, event: wx.CommandEvent | None) -> None:
        """Handle generate docset action."""
        if self.selected_row_index is None:
            wx.MessageBox(
                "Please select a package from the grid.",
                "No Selection",
                wx.OK | wx.ICON_INFORMATION,
            )
            if event:
                event.Skip()
            return

        selected_package_data = self.get_selected_row()
        if not selected_package_data:
            wx.MessageBox(
                "Selected package data not found.",
                "Internal Error",
                wx.OK | wx.ICON_ERROR,
            )
            if event:
                event.Skip()
            return

        if not self._validate_can_generate(selected_package_data):
            if event:
                event.Skip()
            return

        self._initiate_generation_task(selected_package_data, self.selected_row_index)

        if event:
            event.Skip()

    def _stop_animation_timer_if_no_tasks(self) -> None:
        """Stop the animation timer if no generation tasks are active."""
        if self.animation_timer and not self.active_generation_tasks:
            self.animation_timer.Stop()
            self.current_animation_frame_idx = 0
            logger.debug("No remaining active task, animation timer stopped.")

    def _log_generation_outcome_and_notify(
        self, success: bool, message: str, package_name: Optional[str]
    ) -> None:
        """Log the generation outcome and notifies the user via message box."""
        if success:
            log_message_to_append = (
                f"SUCCESS: Generation for '{package_name}' completed. {message}\n"
            )
        else:
            log_message_to_append = (
                f"ERROR: Generation per '{package_name}' failed. {message}\n"
            )
            wx.MessageBox(
                f"Error during generation for '{package_name}':\n{message}",
                "Error di Generation",
                wx.OK | wx.ICON_ERROR,
            )

        if self.log_text_ctrl:
            self.log_text_ctrl.AppendText(log_message_to_append)

    def _update_grid_with_generation_status(
        self, row_idx: int, status_text: str
    ) -> None:
        """Update the data grid and source data for the completed generation task."""
        if not self.data_grid:
            return
        if self.docset_status_col_grid_idx == -1:
            return

        if 0 <= row_idx < self.data_grid.GetNumberRows():
            self.data_grid.SetCellValue(
                row_idx,
                self.docset_status_col_grid_idx,
                status_text,
            )
            if 0 <= row_idx < len(self.current_grid_source_data):
                self.current_grid_source_data[row_idx]["docset_status"] = status_text
            self.data_grid.ForceRefresh()


    def _on_generation_complete(
        self,
        success: bool,
        message: str,
        package_name: Optional[str],
        package_id: Optional[str],
    ) -> None:
        """Handle il completion di un task di generation.

        Questo method is executed in main GUI thread using wx.CallAfter.
        """
        if not package_id:
            self._stop_animation_timer_if_no_tasks()
            self._update_action_buttons_state()
            return

        row_idx_to_update = self.active_generation_tasks.pop(package_id, -1)

        self._stop_animation_timer_if_no_tasks()
        self._log_generation_outcome_and_notify(success, message, package_name)

        final_status_text = "📖 Available" if success else "❌ Error"

        if row_idx_to_update != -1:
            self._update_grid_with_generation_status(
                row_idx_to_update, final_status_text
            )
            if success and 0 <= row_idx_to_update < len(
                self.current_grid_source_data
            ):
                self.current_grid_source_data[row_idx_to_update]["docset_path"] = (
                    message
                )
                logger.info(
                    f"GUI: Docset path '{message}' stored for package "
                    f"'{package_name}' at row {row_idx_to_update}"
                )

        self._update_action_buttons_state()

    def _perform_generation_in_thread(self, package_data: dict) -> None:
        """Execute la generation del docset in a separated thread.

        Calls core e send il result alla GUI using wx.CallAfter.
        """
        package_name_for_msg = package_data.get("name", "N/D")
        package_id_for_completion = package_data.get("id")

        if not package_id_for_completion:
            return

        try:
            if not self.core:
                error_message = "Error nel thread: Instance Core non disponibile."
                wx.CallAfter(
                    self._on_generation_complete,
                    False,
                    error_message,
                    package_name_for_msg,
                    package_id_for_completion,
                )
                return
            success, message = self.core.generate_docset(package_data)
            wx.CallAfter(
                self._on_generation_complete,
                success,
                message,
                package_name_for_msg,
                package_id_for_completion,
            )

        except Exception as e:
            error_message = ("Unexpected Exception durante la generation per "
                             f"'{package_name_for_msg}' nel thread: {e}")
            wx.CallAfter(
                self._on_generation_complete,
                False,
                error_message,
                package_name_for_msg,
                package_id_for_completion,
            )

    def on_regenerate_docset(self, event: wx.CommandEvent) -> None:
        """Handle regenerate docset action.

        This will attempt to delete the existing docset
            (if one exists and user confirms via on_delete_docset)
        and then trigger a new generation.
        """
        if self.selected_row_index is None:
            wx.MessageBox(
                "Please select a package to regenerate its docset.",
                "No Selection",
                wx.OK | wx.ICON_INFORMATION,
            )
            if event:
                event.Skip()
            return

        selected_package_data_initial = self.get_selected_row()
        if not selected_package_data_initial:
            wx.MessageBox(
                "Could not retrieve data for the selected row.",
                "Internal Error",
                wx.OK | wx.ICON_ERROR,
            )
            if event:
                event.Skip()
            return

        package_name = selected_package_data_initial.get("name", "N/D")
        current_status = selected_package_data_initial.get(
            "docset_status", "Not Available")
        package_id = selected_package_data_initial.get("id")

        if package_id in self.active_generation_tasks:
            wx.MessageBox(
                f"A task for '{package_name}' is already in progress. "
                "Cannot regenerate now.",
                "Task Active",
                wx.OK | wx.ICON_INFORMATION,
            )
            if event:
                event.Skip()
            return

        # Log the intent to regenerate
        log_msg = (f"INFO: Regeneration requested for '{package_name}'. "
                   f"Current status: {current_status}.\n")
        if self.log_text_ctrl:
            self.log_text_ctrl.AppendText(log_msg)
        if current_status in ["📖 Available", "❌ Error"]:
            self.on_delete_docset(event=None)

        self.on_generate_docset(event=None)

        if event:
            event.Skip()

    def on_view_log(self, event: wx.CommandEvent) -> None:
        """Handle view log action."""
        sel_data = self.get_selected_row()
        if sel_data:
            logger.info(sel_data)
            if not self.is_log_panel_visible:
                self._set_log_panel_visibility(True)
        event.Skip()


    def on_delete_docset(self, event: wx.CommandEvent | None) -> None:
        """Handle delete docset action."""
        selected_package_data = self.get_selected_row()
        package_name = selected_package_data.get("name", "N/D")
        docset_path_str = selected_package_data.get("docset_path")
        path_of_specific_docset_build = Path(docset_path_str)
        package_level_docset_dir = path_of_specific_docset_build.parent
        confirm_dialog = wx.MessageDialog(
            self.main_frame,
            "Are you sure you want to delete this specific docset build for"
            f" '{package_name}'?\n"
            f"Path: {path_of_specific_docset_build}\n\n"
            f"If this is the last docset in the '{package_name}' directory, "
            f"the entire '{package_name}' directory will also be removed.\n\n"
            "This action cannot be undone.",
            "Confirm Deletion",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )

        user_choice = confirm_dialog.ShowModal()
        confirm_dialog.Destroy()

        if user_choice == wx.ID_YES:
            log_message = ""
            try:
                shutil.rmtree(path_of_specific_docset_build)
                if (
                    package_level_docset_dir.exists()
                    and package_level_docset_dir.is_dir()
                    and not list(package_level_docset_dir.iterdir())
                ):
                    shutil.rmtree(package_level_docset_dir)

                self.current_grid_source_data[self.selected_row_index][
                    "docset_status"
                ] = "Not Available"
                self.current_grid_source_data[
                    self.selected_row_index
                ].pop("docset_path", None)
                self.data_grid.SetCellValue(
                    self.selected_row_index,
                    self.docset_status_col_grid_idx,
                    "Not Available",
                )
                self.data_grid.ForceRefresh()
                wx.MessageBox(
                    f"The selected docset build for '{package_name}'"
                    f" has been processed.\n"
                    "Check logs for details.",
                    "Deletion Processed",
                    wx.OK | wx.ICON_INFORMATION,
                )

            except OSError as e:
                log_message += (
                    f"ERROR: Failed to delete files/directories for '{package_name}'. "
                    f"Attempted path(s): '{path_of_specific_docset_build}' and possibly"
                    f" '{package_level_docset_dir}'. Error: {e}\n"
                )
                wx.MessageBox(
                    "Could not complete the deletion process for"
                    f" '{package_name}'.\n"
                    f"Error: {e}",
                    "Deletion Failed",
                    wx.OK | wx.ICON_ERROR,
                )

            if self.log_text_ctrl and log_message:
                self.log_text_ctrl.AppendText(log_message)

            self._update_action_buttons_state()


        event.Skip()
    def on_log_toggle_button_click(self, event: wx.CommandEvent) -> None:
        """Toggle visibility of the log panel."""
        self._set_log_panel_visibility(not self.is_log_panel_visible)
        event.Skip()

    def on_grid_cell_click(self, event: wx.grid.GridEvent) -> None:
        """Handle click on a grid cell."""
        if not self.data_grid or not self.custom_row_highlight_attr:
            if event:
                event.Skip()
            return
        clicked_row = event.GetRow()
        if (
            self.custom_highlighted_row_index is not None
            and self.custom_highlighted_row_index != clicked_row
        ):
            self.data_grid.SetRowAttr(self.custom_highlighted_row_index, None)
            if self.data_grid.GetNumberRows() > self.custom_highlighted_row_index:
                self.data_grid.SetCellValue(
                    self.custom_highlighted_row_index, self.indicator_col_idx, ""
                )
        if self.data_grid.GetNumberRows() > clicked_row >= 0:
            self.data_grid.SetCellValue(clicked_row, self.indicator_col_idx, "►")
            self.custom_row_highlight_attr.IncRef()
            self.data_grid.SetRowAttr(clicked_row, self.custom_row_highlight_attr)
            self.custom_highlighted_row_index = clicked_row
            self.selected_row_index = clicked_row
        self.data_grid.ForceRefresh()
        grid_row_data = []
        if self.data_grid:
            num_columns = self.data_grid.GetNumberCols()
            for col_idx in range(num_columns):
                grid_row_data.append(self.data_grid.GetCellValue(clicked_row, col_idx))

        self._update_action_buttons_state()
        event.Skip()

    def _setup_navigation_panel(self, panel: wx.Panel) -> wx.Sizer:
        icon_size = wx.DefaultSize
        back_icon = wx.ArtProvider.GetBitmap(wx.ART_GO_BACK, wx.ART_BUTTON, icon_size)
        forward_icon = wx.ArtProvider.GetBitmap(
            wx.ART_GO_FORWARD, wx.ART_BUTTON, icon_size
        )
        home_icon = wx.ArtProvider.GetBitmap(wx.ART_GO_HOME, wx.ART_BUTTON, icon_size)
        self.back_button = wx.Button(panel)
        self.forward_button = wx.Button(panel)
        self.home_button = wx.Button(panel)
        if back_icon.IsOk():
            self.back_button.SetBitmap(back_icon, wx.LEFT)
        if forward_icon.IsOk():
            self.forward_button.SetBitmap(forward_icon, wx.LEFT)
        if home_icon.IsOk():
            self.home_button.SetBitmap(home_icon, wx.LEFT)
        self.back_button.Bind(wx.EVT_BUTTON, self.on_back)
        self.forward_button.Bind(wx.EVT_BUTTON, self.on_forward)
        self.home_button.Bind(wx.EVT_BUTTON, self.go_home)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.back_button, 0, wx.ALL, 5)
        button_sizer.Add(self.forward_button, 0, wx.ALL, 5)
        button_sizer.Add(self.home_button, 0, wx.ALL, 5)
        return button_sizer

    def on_webview_navigated(self, event: wx.html2.WebViewEvent) -> None:
        """Handle page change event to update their state."""
        self.update_navigation_buttons_state()
        event.Skip()

    def update_navigation_buttons_state(self) -> None:
        """Update navigation buttons state."""
        if self.webview and self.back_button and self.forward_button:
            self.back_button.Enable(self.webview.CanGoBack())
            self.forward_button.Enable(self.webview.CanGoForward())

    def on_back(self, event: wx.CommandEvent) -> None:
        """Handle browser back button click."""
        if event:
            event.Skip()
        if self.webview.CanGoBack():
            self.webview.GoBack()

    def get_selected_row(self) -> dict | None:
        """Get selected row data."""
        if self.selected_row_index is not None and 0 <= self.selected_row_index < len(
            self.current_grid_source_data
        ):
            return self.current_grid_source_data[self.selected_row_index]
        return None

    def _update_log_toggle_button_icon(self) -> None:
        if not self.log_toggle_button:
            return

        target_bmp_to_use = wx.NullBitmap

        if self.is_log_panel_visible:
            if self.arrow_down_bmp_scaled and self.arrow_down_bmp_scaled.IsOk():
                target_bmp_to_use = self.arrow_down_bmp_scaled
            elif self.arrow_down_bmp and self.arrow_down_bmp.IsOk():
                target_bmp_to_use = self.arrow_down_bmp
        elif self.arrow_up_bmp_scaled and self.arrow_up_bmp_scaled.IsOk():
            target_bmp_to_use = self.arrow_up_bmp_scaled
        elif self.arrow_up_bmp and self.arrow_up_bmp.IsOk():
            target_bmp_to_use = self.arrow_up_bmp

        if isinstance(self.log_toggle_button, wx.BitmapButton):
            self.log_toggle_button.SetBitmap(target_bmp_to_use)

    def update_grid(self) -> None:
        """Populate self.data_grid con i dati."""
        self.selected_row_index = None
        self.custom_highlighted_row_index = None
        table_data = self.current_grid_source_data

        num_rows = len(table_data)
        current_grid_rows = self.data_grid.GetNumberRows()
        if current_grid_rows < num_rows:
            self.data_grid.AppendRows(num_rows - current_grid_rows)
        elif current_grid_rows > num_rows:
            self.data_grid.DeleteRows(
                num_rows, current_grid_rows - num_rows
            )

        for r_idx, row_dict in enumerate(table_data):
            for c_idx, col_name in enumerate(COLUMNS_ORDER):
                cell_value = row_dict.get(col_name, "")
                self.data_grid.SetCellValue(r_idx, c_idx + 1, str(cell_value))
        self.data_grid.ForceRefresh()

    def on_forward(self, event: wx.CommandEvent) -> None:
        """Handle browser forward button click."""
        if event:
            event.Skip()
        if self.webview.CanGoForward():
            self.webview.GoForward()

    def load_url(self, url_to_load: str) -> None:
        """Load in webview given url."""
        if self.webview:
            self.webview.LoadURL(url_to_load)

    def _clear_main_panel(self) -> None:
        """Clear il main_panel_sizer e empties references to widget."""
        if self.main_panel_sizer and self.main_panel_sizer.GetItemCount() > 0:
            self.main_panel_sizer.Clear(True)
        self.webview = None
        self.back_button = None
        self.forward_button = None
        self.home_button = None
        self.data_grid = None
        self.selected_row_index = None
        self.custom_highlighted_row_index = None
        self.open_action_button = None
        self.generate_action_button = None
        self.regenerate_action_button = None
        self.view_log_action_button = None
        self.delete_action_button = None
        self.log_text_ctrl = None
        self.log_toggle_button = None
        self.is_log_panel_visible = False
        self.package_display_label = None
        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()

    def _update_action_buttons_state(self) -> None:
        """Update state (enabled/disabled) of action buttons."""
        self.is_task_running = bool(self.active_generation_tasks)

        action_buttons = {
            "open": self.open_action_button,
            "generate": self.generate_action_button,
            "regenerate": self.regenerate_action_button,
            "log": self.view_log_action_button,
            "delete": self.delete_action_button,
        }

        if self.selected_row_index is None:
            for button_widget in action_buttons.values():
                if button_widget:
                    button_widget.Enable(False)
        else:
            selected_package_data = self.get_selected_row()
            if selected_package_data:
                self._set_button_states_for_selected_row(
                    selected_package_data, action_buttons
                )
            else:
                for button_widget in action_buttons.values():
                    if button_widget:
                        button_widget.Enable(False)
        disable_if_any_task_running = self.is_task_running
        if self.home_button:
            self.home_button.Enable(not disable_if_any_task_running)

    def _validate_can_generate(self, package_data: dict) -> bool:
        """Validate if generation can start for the given package data.

        Shows message boxes for validation failures.
        Returns True if all checks pass, False otherwise.
        """
        package_id = package_data.get("id")
        package_name = package_data.get("name", "N/D")

        if not package_id:
            wx.MessageBox(
                "Package ID missing for the selected row.",
                "Data Error",
                wx.OK | wx.ICON_ERROR,
            )
            return False

        if package_id in self.active_generation_tasks:
            wx.MessageBox(
                f"Generation for '{package_name}' is already in progress.",
                "Generation Active",
                wx.OK | wx.ICON_INFORMATION,
            )
            return False

        current_status = package_data.get("docset_status", "Not Available")
        if current_status == "📖 Available":
            wx.MessageBox(
                f"The docset for '{package_name}' is already available.",
                "Already Available",
                wx.OK | wx.ICON_INFORMATION,
            )
            return False

        if not self.core:
            wx.MessageBox(
                "Core component non è initialized. Unable to generate.",
                "Error Critical",
                wx.OK | wx.ICON_ERROR,
            )
            return False
        return True

    def _initiate_generation_task(self, package_data: dict, row_index: int) -> None:
        """Initiate the UI updates and starts the generation thread."""
        package_id = package_data.get("id")

        self.active_generation_tasks[package_id] = row_index
        self._update_action_buttons_state()
        if (
            self.data_grid
            and self.docset_status_col_grid_idx != -1
            and 0 <= row_index < self.data_grid.GetNumberRows()
            and 0 <= row_index < len(self.current_grid_source_data)
        ):

            first_animation_frame = self.animation_frames[0]
            self.data_grid.SetCellValue(
                row_index,
                self.docset_status_col_grid_idx,
                first_animation_frame,
            )
            self.current_grid_source_data[row_index][
                "docset_status"
            ] = first_animation_frame
            self.data_grid.ForceRefresh()

        if self.animation_timer and not self.animation_timer.IsRunning():
            self.animation_timer.Start(150)

        thread_package_data = package_data.copy()
        worker = threading.Thread(
            target=self._perform_generation_in_thread, args=(thread_package_data,)
        )
        worker.daemon = True
        worker.start()

    def _setup_action_buttons_panel(self, parent: wx.Window) -> wx.Sizer:
        action_box = wx.StaticBox(parent, label="Docset Actions")
        static_box_sizer = wx.StaticBoxSizer(action_box, wx.VERTICAL)
        buttons_internal_sizer = wx.BoxSizer(wx.VERTICAL)

        button_definitions = [
            ("Open Docset 📖", "open_action_button", self.on_open_docset),
            ("Generate Docset 🛠️", "generate_action_button", self.on_generate_docset),
            (
                "Regenerate Docset 🔄",
                "regenerate_action_button",
                self.on_regenerate_docset,
            ),
            ("View Error Log 📄", "view_log_action_button", self.on_view_log),
            ("Delete Docset 🗑️", "delete_action_button", self.on_delete_docset),
        ]
        for label_text, attr_name, handler in button_definitions:
            # Usa il wx.Button standard
            button = wx.Button(action_box, label=label_text)
            setattr(self, attr_name, button)

            button.Bind(wx.EVT_BUTTON, handler)
            buttons_internal_sizer.Add(button, 0, wx.EXPAND | wx.ALL, 5)
            button.Enable(False)

        static_box_sizer.Add(buttons_internal_sizer, 1, wx.EXPAND | wx.ALL, 5)
        return static_box_sizer
def main() -> None:
    """Launch whole application."""
    core = DevilDexCore()
    DevilDexApp(core=core, initial_url="https://www.gazzetta.it")


if __name__ == "__main__":
    main()
