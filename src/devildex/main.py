"""main application."""

import logging
from pathlib import Path
from typing import Any, Optional

import wx
import wx.grid
import wx.html2
from wx import Size

from devildex.constants import AVAILABLE_BTN_LABEL, COLUMNS_ORDER, ERROR_BTN_LABEL
from devildex.core import DevilDexCore
from devildex.default_data import PACKAGES_DATA_AS_DETAILS
from devildex.models import PackageDetails
from devildex.task_manager import GenerationTaskManager
from devildex.ui import ActionsPanel, DocsetGridPanel, DocumentViewPanel

logger = logging.getLogger(__name__)

NO_SELECTION_MSG = "No Selection"
INTERNAL_ERROR_MSG = "Internal Error"
NOT_AVAILABLE_BTN_LABEL = "Not Available"


class GuiLogHandler(logging.Handler):
    """Class define Gui Log Handler."""

    def __init__(self, text_ctrl: wx.TextCtrl) -> None:
        """Construct GuiLogHandler class."""
        super().__init__()
        self.text_ctrl = text_ctrl
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
        )
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log message."""
        # noinspection PyUnresolvedReferences
        try:
            msg = self.format(record)
            # noinspection PyArgumentList
            if self.text_ctrl and wx.IsMainThread():
                self.text_ctrl.AppendText(msg + "\n")
            elif self.text_ctrl:
                wx.CallAfter(self.text_ctrl.AppendText, msg + "\n")
        except (
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
            RuntimeError,
            # noinspection PyUnresolvedReferences
            wx.AssertionError,
        ):
            self.handleError(record)


class DevilDexApp(wx.App):
    """Main Application."""

    def __init__(
        self,
        core: DevilDexCore | None = None,
        initial_url: str | None = None,
    ) -> None:
        """Construct DevilDexApp class."""
        self.document_view_panel = None
        self.gui_log_handler = None
        self.jokes_timer = None
        self.core = core
        self.home_url = "https://www.google.com"
        self.initial_url = initial_url
        self.main_frame: Optional[wx.Frame] = None
        self.panel: Optional[wx.Panel] = None
        self.main_panel_sizer: Optional[wx.BoxSizer] = None
        self.current_grid_source_data: list[dict[str, Any]] = []
        self.actions_panel: ActionsPanel | None = None
        self.selected_row_index: int | None = None
        self.log_text_ctrl: Optional[wx.TextCtrl] = None
        self.is_log_panel_visible: bool = False
        self.log_toggle_button: Optional[wx.Button] = None
        self.arrow_up_bmp: Optional[wx.Bitmap] = None
        self.arrow_down_bmp: Optional[wx.Bitmap] = None
        self.is_task_running: bool = False
        self.docset_status_col_grid_idx: int = -1
        self.arrow_up_bmp_scaled: Optional[wx.Bitmap] = None
        self.arrow_down_bmp_scaled: Optional[wx.Bitmap] = None
        self.view_mode_selector: Optional[wx.ComboBox] = None
        self.grid_panel: DocsetGridPanel | None = None
        self.splitter: Optional[wx.SplitterWindow] = None
        self.top_splitter_panel: Optional[wx.Panel] = None
        self.bottom_splitter_panel: Optional[wx.Panel] = None
        self.last_sash_position: int = -200
        self.generation_task_manager: Optional[GenerationTaskManager] = None

        super().__init__(redirect=False)

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

    def _confirm_deletion(self, package_name: str, docset_path: str) -> bool:
        """Show a confirmation dialog for deletion.

        Returns:
            True if the user clicks 'Yes', False otherwise.

        """
        confirm_dialog = wx.MessageDialog(
            self.main_frame,
            f"Are you sure you want to delete the docset for '{package_name}'?\n"
            f"Path: {docset_path}\n\n"
            "This action cannot be undone.",
            "Confirm Deletion",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        user_choice = confirm_dialog.ShowModal()
        confirm_dialog.Destroy()
        return user_choice == wx.ID_YES

    def _update_grid_after_delete(self) -> None:
        """Update the data source and the grid UI after a successful deletion."""
        if self.selected_row_index is None:
            return

        # Update the in-memory data source first
        self.current_grid_source_data[self.selected_row_index][
            "docset_status"
        ] = NOT_AVAILABLE_BTN_LABEL
        self.current_grid_source_data[self.selected_row_index].pop("docset_path", None)

        # Then, update the visual grid component
        if self.grid_panel and self.grid_panel.grid:
            self.grid_panel.grid.SetCellValue(
                self.selected_row_index,
                self.docset_status_col_grid_idx,
                NOT_AVAILABLE_BTN_LABEL,
            )
            self.grid_panel.grid.ForceRefresh()

    def _handle_delete_success(self, package_name: str) -> None:
        """Handle all UI updates after a successful docset deletion."""
        logger.info(f"GUI: Successfully deleted docset for '{package_name}'.")
        wx.MessageBox(
            f"The docset for '{package_name}' has been deleted.",
            "Deletion Successful",
            wx.OK | wx.ICON_INFORMATION,
        )
        self._update_grid_after_delete()

    def _display_mcp_warning_in_gui(self) -> None:
        """Display a warning message box for the MCP server in GUI mode."""
        wx.MessageBox(
            "The MCP server is currently experimental in all modes (GUI and headless).\n\n"
            "It has limited functionality and is primarily for development and testing.",
            "MCP Server: Experimental",
            wx.OK | wx.ICON_INFORMATION,
        )

    @staticmethod
    def _handle_delete_failure(package_name: str, message: str) -> None:
        """Handle UI updates after a failed docset deletion."""
        logger.error(
            f"GUI: Core failed to delete docset for '{package_name}'. Reason: {message}"
        )
        wx.MessageBox(
            f"Could not delete the docset for '{package_name}'.\n\n"
            f"Reason: {message}",
            "Deletion Failed",
            wx.OK | wx.ICON_ERROR,
        )

    @staticmethod
    def matching_docset(pkg: str, grid_pkg: dict) -> bool:
        """Check if a package name is matching a package in grid."""
        return pkg == grid_pkg.get("name")

    @staticmethod
    def _docset_scan_subdir(
        subdirs_to_check: list,
        package_root_on_disk: Path,
    ) -> Path | None:
        for subdir_candidate_name in subdirs_to_check:
            potential_docset_path = package_root_on_disk / subdir_candidate_name
            if potential_docset_path.exists() and potential_docset_path.is_dir():
                found_specific_docset_subdir = potential_docset_path
                return found_specific_docset_subdir
        return None

    @staticmethod
    def _docset_scan_set_status(
        found_specific_docset_subdir: Path | None,
        pkg_data: dict,
    ) -> None:
        if found_specific_docset_subdir:
            pkg_data["docset_status"] = AVAILABLE_BTN_LABEL
            pkg_data["docset_path"] = str(found_specific_docset_subdir.resolve())
        else:
            pkg_data["docset_status"] = NOT_AVAILABLE_BTN_LABEL
            pkg_data.pop("docset_path", None)

    def _perform_startup_docset_scan(self) -> None:
        """Execute the scan dei existing docsets on startup e updates.

        self.current_grid_source_data.
        """
        matched_top_level_dir_names: set[str] = self.scan_docset_dir(
            self.current_grid_source_data
        )
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
                found_specific_docset_subdir: Optional[Path] = self._docset_scan_subdir(
                    subdirs_to_check,
                    package_root_on_disk,
                )
                self._docset_scan_set_status(found_specific_docset_subdir, pkg_data)
            else:
                pkg_data["docset_status"] = NOT_AVAILABLE_BTN_LABEL
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

        if self.splitter and self.splitter.IsShown():
            self.splitter.Hide()

        if self.document_view_panel and not self.document_view_panel.IsShown():
            self.document_view_panel.Show()

        if not self.panel or not self.main_panel_sizer or not self.document_view_panel:
            logger.error("GUI: Main panel not ready for document view.")
            return

        new_label_text = "Viewing documentation"
        if package_data_to_show:
            package_name = package_data_to_show.get("name", "Unknown Package")
            new_label_text = package_name

        self.document_view_panel.set_document_title(new_label_text)

        if self.initial_url:
            self.document_view_panel.load_url(self.initial_url)

        if self.panel:
            self.panel.Layout()

    def _init_buttons(self) -> None:
        original_icon_size = Size(16, 16)
        scaled_icon_height = 8
        self.arrow_down_bmp = wx.ArtProvider.GetBitmap(
            wx.ART_GO_DOWN, wx.ART_BUTTON, original_icon_size
        )
        self.arrow_up_bmp = wx.ArtProvider.GetBitmap(
            wx.ART_GO_UP, wx.ART_BUTTON, original_icon_size
        )
        scaled_icon_width = scaled_icon_height
        scaled_icon_target_size = (scaled_icon_width, scaled_icon_height)
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

    def OnInit(self) -> bool:  # noqa: N802
        """Set up gui widgets on application startup."""
        wx.Log.SetActiveTarget(wx.LogStderr())
        window_title = "DevilDex"
        self.main_frame = wx.Frame(
            parent=None, title=window_title, size=Size(1280, 900)
        )
        self.panel = wx.Panel(self.main_frame)
        self.main_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.main_panel_sizer)
        self.main_frame.Centre()
        self.SetTopWindow(self.main_frame)

        self._init_buttons()

        # --- Start of refactored view setup ---
        # Create all main view components once
        view_mode_sizer = self._setup_view_mode_selector(self.panel)
        self.main_panel_sizer.Add(
            view_mode_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5
        )

        self._init_splitter_components(self.panel)  # This creates self.splitter
        if self.splitter:
            self.main_panel_sizer.Add(self.splitter, 1, wx.EXPAND | wx.ALL, 5)

        self.document_view_panel = DocumentViewPanel(self.panel, self.go_home)
        self.main_panel_sizer.Add(self.document_view_panel, 1, wx.EXPAND | wx.ALL, 5)
        self.document_view_panel.Hide()

        bottom_bar_sizer = self._init_log_toggle_bar(self.panel)
        self.main_panel_sizer.Add(bottom_bar_sizer, 0, wx.EXPAND | wx.ALL, 0)

        self.init_log()
        if self.gui_log_handler and self.log_text_ctrl:
            self.gui_log_handler.text_ctrl = self.log_text_ctrl
        self._update_log_toggle_button_icon()

        self.main_frame.Show(True)

        self.jokes_timer = wx.Timer(self)
        return True

    def init_log(self) -> None:
        """Initialize log."""
        self.gui_log_handler = GuiLogHandler(self.log_text_ctrl)
        devildex_package_logger = logging.getLogger("devildex")
        if self.gui_log_handler not in devildex_package_logger.handlers:
            devildex_package_logger.addHandler(self.gui_log_handler)
        devildex_package_logger.setLevel(logging.INFO)

        for h in logger.handlers[:]:
            logger.removeHandler(h)
        logger.addHandler(self.gui_log_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    def go_home(self, event: wx.CommandEvent | None = None) -> None:
        """Go to initial view."""
        if event:
            event.Skip()

        if self.document_view_panel and self.document_view_panel.IsShown():
            self.document_view_panel.Hide()

        if self.splitter and not self.splitter.IsShown():
            self.splitter.Show()

        if self.panel:
            self.panel.Layout()

    def _setup_view_mode_selector(self, parent: wx.Window) -> wx.Sizer:
        """Configura il ComboBox per la selection della mode di vista."""
        view_choices = ["Show all Docsets (Global)"]
        if self.core:
            project_names_from_db = self.core.query_project_names()
            for name in project_names_from_db:
                view_choices.append(f"Project: {name}")
        else:
            logger.error(
                "GUI: DevilDexCore non disponibile durante _setup_view_mode_selector."
            )

        self.view_mode_selector = wx.ComboBox(
            parent,
            choices=view_choices,
            style=wx.CB_READONLY,
        )
        self.view_mode_selector.SetValue(view_choices[0])

        selector_sizer = wx.BoxSizer(wx.HORIZONTAL)
        selector_label = wx.StaticText(parent, label="View Mode:")
        selector_sizer.Add(selector_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        selector_sizer.Add(self.view_mode_selector, 1, wx.EXPAND)
        self.view_mode_selector.Bind(wx.EVT_COMBOBOX, self.on_view_mode_changed)

        return selector_sizer

    def on_view_mode_changed(self, event: wx.CommandEvent) -> None:
        """Handle view mode change from the ComboBox."""
        if not self._can_process_view_change():
            event.Skip()
            return

        selected_view_str = ""
        if self.view_mode_selector:
            selected_view_str = self.view_mode_selector.GetValue()

        project_successfully_set_in_core = self._handle_core_project_setting(
            selected_view_str
        )

        if not project_successfully_set_in_core:

            event.Skip()
            return

        if not self.core:

            event.Skip()
            return

        self.current_grid_source_data = self.core.bootstrap_database_and_load_data(
            initial_package_source=[],
            is_fallback_data=False,
        )

        self._update_ui_after_data_load()

        if self.panel:
            self.panel.Layout()
        event.Skip()

    def _can_process_view_change(self) -> bool:
        """Check if the necessary components for the view change are available."""
        return not self.view_mode_selector or not self.core

    def _handle_core_project_setting(self, selected_view_str: str) -> bool:
        """Set the active project in the core based on the selection.

        Returns True if the setting is successful, False otherwise.
        """
        if not self.core:
            logger.error("GUI: Core not initialized in _handle_core_project_setting.")
            return False

        success_flag = False

        if selected_view_str == "Show all Docsets (Global)":
            if self.core.set_active_project(None):
                success_flag = True
            else:
                logger.error(
                    "GUI: Unexpected error in setting the global view in the core."
                )
        elif selected_view_str.startswith("Project: "):
            try:
                project_name = selected_view_str.split(": ", 1)[1].strip()
                if self.core.set_active_project(project_name):
                    success_flag = True

            except IndexError:
                logger.exception(
                    "GUI: Could not parse project name from "
                    f"ComboBox selection: {selected_view_str}"
                )

        else:
            logger.error(f"GUI: Unrecognized ComboBox selection: {selected_view_str}")

        return success_flag

    def _determine_initial_packages_for_view(
        self,
    ) -> tuple[list[PackageDetails], bool]:
        """Determine the initial list of PackageDetails, based on the current view."""
        packages_for_db_init: list[PackageDetails]
        is_fallback_data: bool

        if not self.core:
            logger.error(
                "GUI: Core not initialized in _determine_initial_packages_for_view."
            )
            return PACKAGES_DATA_AS_DETAILS, True

        if self.core.registered_project_name:
            scanned_pkgs = self.core.scan_project()

            if scanned_pkgs is not None:
                packages_for_db_init = scanned_pkgs
                is_fallback_data = False
            else:
                packages_for_db_init = PACKAGES_DATA_AS_DETAILS
                is_fallback_data = True
        else:
            packages_for_db_init = []
            is_fallback_data = False
        return packages_for_db_init, is_fallback_data

    def _update_ui_after_data_load(self) -> None:
        """Update UI components after data loading."""
        self.update_grid_data()
        self._perform_startup_docset_scan()
        self._update_action_buttons_state()

    def _init_log_toggle_bar(self, parent_panel: wx.Panel) -> wx.Sizer:
        initial_bmp_to_use = wx.BitmapBundle.FromBitmap(wx.NullBitmap)
        if self.arrow_down_bmp_scaled and self.arrow_down_bmp_scaled.IsOk():
            initial_bmp_to_use = self.arrow_down_bmp_scaled
        elif self.arrow_down_bmp and self.arrow_down_bmp.IsOk():
            initial_bmp_to_use = self.arrow_down_bmp

        button_fixed_size = wx.Size(50, 20)
        self.log_toggle_button = wx.BitmapButton(
            parent_panel,
            id=wx.ID_ANY,
            bitmap=initial_bmp_to_use,
            size=button_fixed_size,
            style=wx.BU_EXACTFIT,
        )
        self.log_toggle_button.Bind(wx.EVT_BUTTON, self.on_log_toggle_button_click)

        bar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bar_sizer.AddStretchSpacer(1)
        button_padding = 0
        bar_sizer.Add(
            self.log_toggle_button,
            proportion=0,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=button_padding,
        )
        sizer_internal_vertical_padding = 0
        desired_bar_height = (
            button_fixed_size.GetHeight() + sizer_internal_vertical_padding
        )
        bar_sizer.SetMinSize(wx.Size(-1, desired_bar_height))
        bar_sizer.AddStretchSpacer(1)
        return bar_sizer

    def _setup_initial_view(self) -> None:
        pass

    def _init_splitter_components(self, parent_panel: wx.Panel) -> None:
        self.splitter = wx.SplitterWindow(
            parent_panel, style=wx.SP_LIVE_UPDATE | wx.SP_BORDER
        )
        self.splitter.SetMinimumPaneSize(50)

        self.top_splitter_panel = wx.Panel(self.splitter)
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.grid_panel = DocsetGridPanel(
            self.top_splitter_panel, self.on_grid_row_selected
        )
        content_sizer.Add(self.grid_panel, 1, wx.EXPAND | wx.ALL, 5)
        self.actions_panel = ActionsPanel(self.top_splitter_panel, self)
        content_sizer.Add(self.actions_panel, 0, wx.EXPAND | wx.ALL, 5)
        self.top_splitter_panel.SetSizer(content_sizer)

        self.bottom_splitter_panel = wx.Panel(self.splitter)
        bottom_splitter_sizer = wx.BoxSizer(wx.VERTICAL)
        self.log_text_ctrl = wx.TextCtrl(
            self.bottom_splitter_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.TE_RICH2,
        )
        bottom_splitter_sizer.Add(self.log_text_ctrl, 1, wx.EXPAND | wx.ALL, 0)
        self.bottom_splitter_panel.SetSizer(bottom_splitter_sizer)

        if self.is_log_panel_visible:
            self.splitter.SplitHorizontally(
                self.top_splitter_panel,
                self.bottom_splitter_panel,
                self.last_sash_position,
            )
            self.top_splitter_panel.Show(True)
            self.bottom_splitter_panel.Show(True)
            if self.log_text_ctrl:
                self.log_text_ctrl.Show(True)
            self.bottom_splitter_panel.Layout()
        else:
            self.splitter.Initialize(self.top_splitter_panel)
            self.top_splitter_panel.Show(True)
            self.bottom_splitter_panel.Show(False)
            if self.log_text_ctrl:
                self.log_text_ctrl.Show(False)

        # In /home/magowiz/MEGA/projects/devildex/src/devildex/main.py

    def _show_log_panel(self) -> None:
        """Handle the logic to make the log panel visible."""
        if (
            not self.splitter
            or not self.top_splitter_panel
            or not self.bottom_splitter_panel
        ):
            return

        if not self.splitter.IsSplit():
            self.splitter.SplitHorizontally(
                self.top_splitter_panel,
                self.bottom_splitter_panel,
                self.last_sash_position,
            )
        self.bottom_splitter_panel.Show(True)
        if self.log_text_ctrl:
            self.log_text_ctrl.Show(True)
        self.splitter.SetSashPosition(self.last_sash_position, redraw=True)
        self.bottom_splitter_panel.Layout()

    def _hide_log_panel(self) -> None:
        """Handle the logic to hide the log panel."""
        if not self.splitter or not self.bottom_splitter_panel:
            return

        if self.splitter.IsSplit():
            self.last_sash_position = self.splitter.GetSashPosition()
            self.splitter.Unsplit(self.bottom_splitter_panel)
        self.bottom_splitter_panel.Show(False)
        if self.log_text_ctrl:
            self.log_text_ctrl.Show(False)

    def _set_log_panel_visibility(self, visible: bool) -> None:
        """Set the visibility of the log panel by dispatching to helper methods."""
        # Guard clause: if the splitter isn't ready, just toggle the text control
        # This handles a potential edge case if called before full UI initialization.
        if not self.splitter:
            if self.log_text_ctrl:
                self.log_text_ctrl.Show(visible)
            if self.panel:
                self.panel.Layout()
            self._update_log_toggle_button_icon()
            return

        self.is_log_panel_visible = visible

        if self.is_log_panel_visible:
            self._show_log_panel()
        else:
            self._hide_log_panel()

        # Final UI updates, common to both actions
        if self.panel:
            self.panel.Layout()
        self._update_log_toggle_button_icon()

    def on_open_docset(self, event: wx.CommandEvent) -> None:
        """Handle open docset action."""
        if self.selected_row_index is None:
            wx.MessageBox(
                "Please select a package from the grid to open its docset.",
                NO_SELECTION_MSG,
                wx.OK | wx.ICON_INFORMATION,
            )
            event.Skip()
            return

        selected_package_data = self.get_selected_row()

        if not selected_package_data:
            wx.MessageBox(
                "Could not retrieve data for the selected row.",
                INTERNAL_ERROR_MSG,
                wx.OK | wx.ICON_ERROR,
            )
            event.Skip()
            return

        docset_path_str = selected_package_data.get("docset_path")
        package_name_for_display = selected_package_data.get("name", "Selected Package")

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
        if self.document_view_panel:
            local_url = index_file_path.as_uri()
            self.document_view_panel.load_url(local_url)
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
                NO_SELECTION_MSG,
                wx.OK | wx.ICON_INFORMATION,
            )
            if event:
                event.Skip()
            return

        selected_package_data = self.get_selected_row()
        if not selected_package_data:
            wx.MessageBox(
                "Selected package data not found.",
                INTERNAL_ERROR_MSG,
                wx.OK | wx.ICON_ERROR,
            )
            if event:
                event.Skip()
            return

        if not self._validate_can_generate(selected_package_data):
            if event:
                event.Skip()
            return

        if self.generation_task_manager:
            task_started = self.generation_task_manager.start_generation_task(
                package_data=selected_package_data,
                row_index=self.selected_row_index,
                docset_status_col_idx=self.docset_status_col_grid_idx,
            )
            if (
                task_started
                and 0 <= self.selected_row_index < len(self.current_grid_source_data)
                and self.generation_task_manager.animation_frames
            ):
                first_frame = self.generation_task_manager.animation_frames[0]
                self.current_grid_source_data[self.selected_row_index][
                    "docset_status"
                ] = first_frame
        else:
            logger.error(
                "GenerationTaskManager not initialized. Cannot generate docset."
            )
            wx.MessageBox(
                "Generation system not ready.", "System Error", wx.OK | wx.ICON_ERROR
            )

        if event:
            event.Skip()

    def _update_grid_cell_from_manager(
        self,
        row_idx: int,
        col_idx: int,
        value: str,
    ) -> None:  # sourcery skip: class-extract-method
        """Call GenerationTaskManager to update a grid cell."""
        if self.grid_panel and self.grid_panel.grid:
            grid = self.grid_panel.grid
            if (
                0 <= row_idx < grid.GetNumberRows()
                and 0 <= col_idx < grid.GetNumberCols()
            ):
                grid.SetCellValue(row_idx, col_idx, value)
            if 0 <= row_idx < len(self.current_grid_source_data) and (
                col_idx == self.docset_status_col_grid_idx
            ):
                self.current_grid_source_data[row_idx]["docset_status"] = value

    def _on_generation_complete_from_manager(
        self,
        success: bool,
        message: str,
        package_name: Optional[str],
        package_id: Optional[str],
        row_idx_to_update: int,
    ) -> None:
        """Handle completion of a generation task, called by GenerationTaskManager."""
        _ = package_id
        if success:
            log_message_to_append = (
                f"SUCCESS: Generation for '{package_name}' completed. {message}\n"
            )
        else:
            log_message_to_append = (
                f"ERROR: Generation for '{package_name}' failed. {message}\n"
            )
            wx.MessageBox(
                f"Error during generation for '{package_name}':\n{message}",
                "Generation Error",
                wx.OK | wx.ICON_ERROR,
            )
        if self.log_text_ctrl:
            self.log_text_ctrl.AppendText(log_message_to_append)

        final_status_text = AVAILABLE_BTN_LABEL if success else ERROR_BTN_LABEL
        if (
            self.grid_panel
            and self.grid_panel.grid
            and self.docset_status_col_grid_idx != -1
            and 0 <= row_idx_to_update < self.grid_panel.grid.GetNumberRows()
        ):
            self.grid_panel.grid.SetCellValue(
                row_idx_to_update,
                self.docset_status_col_grid_idx,
                final_status_text,
            )
            if 0 <= row_idx_to_update < len(self.current_grid_source_data):
                self.current_grid_source_data[row_idx_to_update][
                    "docset_status"
                ] = final_status_text
                if success:
                    self.current_grid_source_data[row_idx_to_update][
                        "docset_path"
                    ] = message

                elif "docset_path" in self.current_grid_source_data[row_idx_to_update]:
                    del self.current_grid_source_data[row_idx_to_update]["docset_path"]

            self.grid_panel.grid.ForceRefresh()

    def on_regenerate_docset(self, event: wx.CommandEvent) -> None:
        """Handle regenerate docset action by chaining delete and generate actions."""
        if self.selected_row_index is None:
            wx.MessageBox(
                "Please select a package to regenerate its docset.",
                NO_SELECTION_MSG,
                wx.OK | wx.ICON_INFORMATION,
            )
            if event:
                event.Skip()
            return

        # Log the user's intent
        selected_package = self.get_selected_row()
        if selected_package:
            package_name = selected_package.get("name", "N/D")
            log_msg = f"INFO: Regeneration requested for '{package_name}'.\n"
            if self.log_text_ctrl:
                self.log_text_ctrl.AppendText(log_msg)

        # 1. Call the delete handler. It will ask for confirmation and handle
        #    all cases (e.g., if the docset doesn't even exist).
        self.on_delete_docset(event=None)

        # 2. Call the generate handler. It will perform its own validation,
        #    like checking if a task is already running or if the docset is
        #    still available (if the user cancelled the deletion).
        self.on_generate_docset(event=None)

        if event:
            event.Skip()

    def OnExit(
        self,
    ) -> int:
        """Perform cleanup before the application terminates."""
        if self.generation_task_manager:
            self.generation_task_manager.cleanup()
        if self.core:
            self.core.shutdown()

        return 0

    def on_view_log(self, event: wx.CommandEvent) -> None:
        """Handle view log action."""
        sel_data = self.get_selected_row()
        if sel_data and not self.is_log_panel_visible:
            self._set_log_panel_visibility(True)
        event.Skip()

    def on_delete_docset(self, event: wx.CommandEvent | None) -> None:
        """Handle delete docset action by delegating to the core."""
        try:
            selected_package_data = self.get_selected_row()
            if not selected_package_data:
                return

            package_name = selected_package_data.get("name", "N/D")
            docset_path_str = selected_package_data.get("docset_path")

            if not docset_path_str:
                wx.MessageBox(
                    f"No docset path found for '{package_name}'. Cannot delete.",
                    "Deletion Error",
                    wx.OK | wx.ICON_ERROR,
                )
                return

            if not self._confirm_deletion(package_name, docset_path_str):
                return

            if not self.core:
                wx.MessageBox(
                    "Core system not available.",
                    INTERNAL_ERROR_MSG,
                    wx.OK | wx.ICON_ERROR,
                )
                return

            success, message = self.core.delete_docset_build(docset_path_str)

            if success:
                self._handle_delete_success(package_name)
            else:
                self._handle_delete_failure(package_name, message)

            self._update_action_buttons_state()
        finally:
            if event:
                event.Skip()

    def _update_action_buttons_state(self) -> None:
        """Update the state of the action buttons by delegating to the ActionsPanel."""
        if self.actions_panel:
            selected_package_data = self.get_selected_row()
            self.actions_panel.update_button_states(
                selected_package_data, self.is_task_running
            )

    def on_log_toggle_button_click(self, event: wx.CommandEvent) -> None:
        """Toggle visibility of the log panel."""
        self._set_log_panel_visibility(not self.is_log_panel_visible)
        event.Skip()

    def on_grid_row_selected(self, row_index: int) -> None:
        """Handle when a row is selected in the DocsetGridPanel."""
        self.selected_row_index = row_index
        self._update_action_buttons_state()

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
        target_bmp_bundle = wx.BitmapBundle.FromBitmap(target_bmp_to_use)

        if isinstance(self.log_toggle_button, wx.BitmapButton):
            self.log_toggle_button.SetBitmap(target_bmp_bundle)

    def update_grid_data(self) -> None:
        """Populate self.data_grid con i dati."""
        self.selected_row_index = None
        if self.grid_panel:
            self.grid_panel.update_data(self.current_grid_source_data)

    def _initialize_data_and_managers(self) -> None:
        """Initialize data and managers that depend on self.core being available."""
        scanned_project_packages: Optional[list[PackageDetails]] = (
            self.core.scan_project()
        )
        scan_successful = bool(scanned_project_packages)
        is_fallback_data = False
        if not scanned_project_packages:
            scanned_project_packages = PACKAGES_DATA_AS_DETAILS
            is_fallback_data = True
        self.current_grid_source_data = self.core.bootstrap_database_and_load_data(
            scanned_project_packages, is_fallback_data
        )
        self._perform_startup_docset_scan()

        self.docset_status_col_grid_idx = COLUMNS_ORDER.index("docset_status") + 1
        self.generation_task_manager = GenerationTaskManager(
            core_instance=self.core,
            owner_for_timer=self.main_frame,
            update_grid_cell_callback=self._update_grid_cell_from_manager,
            on_task_complete_callback=self._on_generation_complete_from_manager,
            update_action_buttons_callback=self._update_action_buttons_state,
        )
        self.update_grid_data()  # Call update_grid_data here after data is loaded

        if scan_successful:
            active_project_file_path = self.core.app_paths.active_project_file
            active_project_file_path.unlink(missing_ok=True)

    def _clear_main_panel(self) -> None:
        pass

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

        if (
            self.generation_task_manager
            and self.generation_task_manager.is_task_active_for_package(package_id)
        ):
            wx.MessageBox(
                f"Generation for '{package_name}' is already in progress.",
                "Generation Active",
                wx.OK | wx.ICON_INFORMATION,
            )
            return False

        current_status = package_data.get("docset_status", NOT_AVAILABLE_BTN_LABEL)
        if current_status == AVAILABLE_BTN_LABEL:
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


import time

from devildex.config_manager import ConfigManager


def main() -> None:
    """Launch whole application."""
    config = ConfigManager()
    mcp_enabled = config.get_mcp_server_enabled()
    hide_gui = config.get_mcp_server_hide_gui_when_enabled()

    if mcp_enabled and hide_gui:
        core = DevilDexCore()
        print("MCP server started in headless mode. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server...")
            core.shutdown()
            print("Server shut down.")
    else:
        app = DevilDexApp()  # Create app instance first

        # Determine if GUI warning callback should be passed
        warning_callback = None
        if (
            mcp_enabled and not hide_gui
        ):  # Only pass if MCP is enabled AND GUI is not hidden
            warning_callback = app._display_mcp_warning_in_gui

        # Create core instance, passing the callback if applicable
        core = DevilDexCore(gui_warning_callback=warning_callback)

        app.core = core  # Set app.core before MainLoop()
        app._initialize_data_and_managers()  # Call the new initialization method
        app.MainLoop()


if __name__ == "__main__":
    main()
