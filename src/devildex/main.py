"""main application."""

import logging
import shutil
from pathlib import Path
from typing import Any, ClassVar, Optional

import wx
import wx.grid
import wx.html2
from wx import Size

from devildex.core import DevilDexCore
from devildex.default_data import COLUMNS_ORDER, PACKAGES_DATA_AS_DETAILS
from devildex.models import PackageDetails
from devildex.task_manager import GenerationTaskManager

logger = logging.getLogger(__name__)
COL_WIDTH_ID = 60
COL_WIDTH_NAME = 160
COL_WIDTH_VERSION = 80
COL_WIDTH_DESC = 200
COL_WIDTH_STATUS = 120
COL_WIDTH_DOCSET_STATUS = 140

AVAILABLE_BTN_LABEL = "📖 Available"
NO_SELECTION_MSG = "No Selection"
INTERNAL_ERROR_MSG = "Internal Error"
ERROR_BTN_LABEL = "❌ Error"


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
        self, core: DevilDexCore | None = None, initial_url: str | None = None
    ) -> None:
        """Construct DevilDexApp class."""
        self.gui_log_handler = None
        self.jokes_timer = None
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
        self.package_display_label: Optional[wx.StaticText] = None
        self.arrow_up_bmp_scaled: Optional[wx.Bitmap] = None
        self.arrow_down_bmp_scaled: Optional[wx.Bitmap] = None
        self.view_mode_selector: Optional[wx.ComboBox] = None

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

    @staticmethod
    def matching_docset(pkg: str, grid_pkg: dict) -> bool:
        """Check if a package name is matching a package in grid."""
        return pkg == grid_pkg.get("name")

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
                found_specific_docset_subdir: Optional[Path] = None
                for subdir_candidate_name in subdirs_to_check:
                    potential_docset_path = package_root_on_disk / subdir_candidate_name
                    if (
                        potential_docset_path.exists()
                        and potential_docset_path.is_dir()
                    ):
                        found_specific_docset_subdir = potential_docset_path
                        break

                if found_specific_docset_subdir:
                    pkg_data["docset_status"] = AVAILABLE_BTN_LABEL
                    pkg_data["docset_path"] = str(
                        found_specific_docset_subdir.resolve()
                    )
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
        scanned_project_packages: Optional[list[PackageDetails]] = (
            self.core.scan_project()
        )
        scan_successful = bool(scanned_project_packages)
        is_fallback_data = False
        if not scanned_project_packages:
            scanned_project_packages = PACKAGES_DATA_AS_DETAILS
            is_fallback_data = True
        self.main_frame = wx.Frame(
            parent=None, title=window_title, size=Size(1280, 900)
        )
        self.current_grid_source_data = self.core.bootstrap_database_and_load_data(
            scanned_project_packages, is_fallback_data
        )
        self.panel = wx.Panel(self.main_frame)
        self.main_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.main_panel_sizer)
        self.main_frame.Centre()
        self.SetTopWindow(self.main_frame)
        self.custom_row_highlight_attr = wx.grid.GridCellAttr()
        self.custom_row_highlight_attr.SetBackgroundColour(wx.Colour(255, 165, 0))
        self.custom_row_highlight_attr.SetTextColour(wx.BLACK)

        self._init_buttons()

        self._perform_startup_docset_scan()

        self.docset_status_col_grid_idx = COLUMNS_ORDER.index("docset_status") + 1
        if self.core:
            self.generation_task_manager = GenerationTaskManager(
                core_instance=self.core,
                owner_for_timer=self.main_frame,
                update_grid_cell_callback=self._update_grid_cell_from_manager,
                on_task_complete_callback=self._on_generation_complete_from_manager,
                update_action_buttons_callback=self._update_action_buttons_state,
            )
        self._setup_initial_view()
        self.init_log()
        self.main_frame.Show(True)
        if scan_successful:
            active_project_file_path = self.core.app_paths.active_project_file
            active_project_file_path.unlink(missing_ok=True)

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

    def _set_button_states_for_selected_row(
        self, package_data: dict, action_buttons: dict
    ) -> None:
        """Help to set states for action buttons based on selected package data."""
        selected_package_id = package_data.get("id")
        current_docset_status = package_data.get("docset_status", "Not Available")
        is_generating_this_row = (
            self.generation_task_manager.is_task_active_for_package(selected_package_id)
            if self.generation_task_manager and selected_package_id
            else False
        )

        open_btn = action_buttons.get("open")
        if open_btn:
            can_open = (
                current_docset_status == AVAILABLE_BTN_LABEL
                and not is_generating_this_row
            )
            open_btn.Enable(can_open)

        generate_btn = action_buttons.get("generate")
        if generate_btn:
            can_generate = (
                not is_generating_this_row
                and current_docset_status != AVAILABLE_BTN_LABEL
            )
            generate_btn.Enable(can_generate)

        regenerate_btn = action_buttons.get("regenerate")
        if regenerate_btn:
            can_regenerate = not is_generating_this_row and current_docset_status in [
                AVAILABLE_BTN_LABEL,
                ERROR_BTN_LABEL,
            ]
            regenerate_btn.Enable(can_regenerate)

        log_btn = action_buttons.get("log")
        if log_btn:
            log_btn.Enable(True)

        delete_btn = action_buttons.get("delete")
        if delete_btn:
            can_delete = not is_generating_this_row and current_docset_status in [
                AVAILABLE_BTN_LABEL,
                ERROR_BTN_LABEL,
            ]
            delete_btn.Enable(can_delete)

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
        self.data_grid.SetColSize(self.indicator_col_idx, 30)
        indicator_attr = wx.grid.GridCellAttr()
        indicator_attr.SetAlignment(wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
        indicator_attr.SetReadOnly(True)
        self.data_grid.SetColAttr(self.indicator_col_idx, indicator_attr.Clone())
        for c_idx, col_name in enumerate(COLUMNS_ORDER):
            grid_col_idx = c_idx + 1
            self.data_grid.SetColLabelValue(grid_col_idx, col_name)
            if col_name in self.COL_WIDTHS:
                self.data_grid.SetColSize(grid_col_idx, self.COL_WIDTHS[col_name])
            col_attr = wx.grid.GridCellAttr()
            col_attr.SetReadOnly(True)
            self.data_grid.SetColAttr(grid_col_idx, col_attr.Clone())

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
        self.update_grid()
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
        self._clear_main_panel()

        if not self.panel or not self.main_panel_sizer:
            logger.error(
                "GUI: Panel or main_panel_sizer not initialized in"
                " _setup_initial_view"
            )
            return

        view_mode_sizer = self._setup_view_mode_selector(self.panel)
        self.main_panel_sizer.Add(
            view_mode_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5
        )

        self._init_splitter_components(self.panel)
        if self.splitter:
            self.main_panel_sizer.Add(self.splitter, 1, wx.EXPAND | wx.ALL, 5)

        bottom_bar_sizer = self._init_log_toggle_bar(self.panel)
        self.main_panel_sizer.Add(bottom_bar_sizer, 0, wx.EXPAND | wx.ALL, 0)

        self.update_grid()

        if self.gui_log_handler and self.log_text_ctrl:
            self.gui_log_handler.text_ctrl = self.log_text_ctrl

        self._update_log_toggle_button_icon()

        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()

    def _init_splitter_components(self, parent_panel: wx.Panel) -> None:
        self.splitter = wx.SplitterWindow(
            parent_panel, style=wx.SP_LIVE_UPDATE | wx.SP_BORDER
        )
        self.splitter.SetMinimumPaneSize(50)

        self.top_splitter_panel = wx.Panel(self.splitter)
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.data_grid = wx.grid.Grid(self.top_splitter_panel)
        self.data_grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.on_grid_cell_click)

        if self.data_grid:
            num_data_cols = len(COLUMNS_ORDER)
            total_grid_cols = num_data_cols + 1
            self.data_grid.CreateGrid(0, total_grid_cols)
            self.data_grid.SetSelectionMode(wx.grid.Grid.SelectRows)
            self._configure_grid_columns()

        content_sizer.Add(self.data_grid, 1, wx.EXPAND | wx.ALL, 5)
        action_buttons_sizer = self._setup_action_buttons_panel(self.top_splitter_panel)
        content_sizer.Add(action_buttons_sizer, 0, wx.EXPAND | wx.ALL, 5)
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

    def _set_log_panel_visibility(self, visible: bool) -> None:
        if (
            not self.splitter
            or not self.top_splitter_panel
            or not self.bottom_splitter_panel
        ):

            if self.log_text_ctrl:
                self.log_text_ctrl.Show(visible)
            if self.panel:
                self.panel.Layout()
            self._update_log_toggle_button_icon()
            return

        self.is_log_panel_visible = visible

        if self.is_log_panel_visible:
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
        else:
            if self.splitter.IsSplit():
                self.last_sash_position = self.splitter.GetSashPosition()
                self.splitter.Unsplit(self.bottom_splitter_panel)
            self.bottom_splitter_panel.Show(False)
            if self.log_text_ctrl:
                self.log_text_ctrl.Show(False)

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
        self, row_idx: int, col_idx: int, value: str
    ) -> None:
        """Call GenerationTaskManager to update a grid cell."""
        if not self.data_grid:
            return
        if (
            0 <= row_idx < self.data_grid.GetNumberRows()
            and 0 <= col_idx < self.data_grid.GetNumberCols()
        ):
            self.data_grid.SetCellValue(row_idx, col_idx, value)
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

        final_status_text = AVAILABLE_BTN_LABEL if success else "❌ Error"
        if (
            self.data_grid
            and self.docset_status_col_grid_idx != -1
            and 0 <= row_idx_to_update < self.data_grid.GetNumberRows()
        ):
            self.data_grid.SetCellValue(
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

            self.data_grid.ForceRefresh()

    def on_regenerate_docset(self, event: wx.CommandEvent) -> None:
        """Handle regenerate docset action.

        This will attempt to delete the existing docset
            (if one exists and user confirms via on_delete_docset)
        and then trigger a new generation.
        """
        if self.selected_row_index is None:
            wx.MessageBox(
                "Please select a package to regenerate its docset.",
                NO_SELECTION_MSG,
                wx.OK | wx.ICON_INFORMATION,
            )
            if event:
                event.Skip()
            return

        selected_package_data_initial = self.get_selected_row()
        if not selected_package_data_initial:
            wx.MessageBox(
                "Could not retrieve data for the selected row.",
                INTERNAL_ERROR_MSG,
                wx.OK | wx.ICON_ERROR,
            )
            if event:
                event.Skip()
            return

        package_name = selected_package_data_initial.get("name", "N/D")
        current_status = selected_package_data_initial.get(
            "docset_status", "Not Available"
        )
        package_id = selected_package_data_initial.get("id")
        if (
            self.generation_task_manager
            and self.generation_task_manager.is_task_active_for_package(package_id)
        ):
            wx.MessageBox(
                f"A task for '{package_name}' is already in progress. "
                "Cannot regenerate now.",
                "Task Active",
                wx.OK | wx.ICON_INFORMATION,
            )
            if event:
                event.Skip()
            return

        log_msg = (
            f"INFO: Regeneration requested for '{package_name}'. "
            f"Current status: {current_status}.\n"
        )
        if self.log_text_ctrl:
            self.log_text_ctrl.AppendText(log_msg)
        if current_status in [AVAILABLE_BTN_LABEL, "❌ Error"]:
            self.on_delete_docset(event=None)

        self.on_generate_docset(event=None)

        if event:
            event.Skip()

    def OnExit(  # noqa: N802
        self,
    ) -> int:
        """Perform cleanup before the application terminates."""
        if self.generation_task_manager:
            self.generation_task_manager.cleanup()

        return 0

    def on_view_log(self, event: wx.CommandEvent) -> None:
        """Handle view log action."""
        sel_data = self.get_selected_row()
        if sel_data and not self.is_log_panel_visible:
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
                self.current_grid_source_data[self.selected_row_index].pop(
                    "docset_path", None
                )
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
            self.data_grid.SetRowAttr(
                self.custom_highlighted_row_index, wx.grid.GridCellAttr()
            )
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
        back_bundle = wx.BitmapBundle(back_icon)
        forward_bundle = wx.BitmapBundle(forward_icon)
        home_bundle = wx.BitmapBundle(home_icon)
        self.forward_button = wx.Button(panel)
        self.home_button = wx.Button(panel)
        if back_icon.IsOk():
            self.back_button.SetBitmap(back_bundle, wx.LEFT)
        if forward_icon.IsOk():
            self.forward_button.SetBitmap(forward_bundle, wx.LEFT)
        if home_icon.IsOk():
            self.home_button.SetBitmap(home_bundle, wx.LEFT)
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
        target_bmp_bundle = wx.BitmapBundle.FromBitmap(target_bmp_to_use)

        if isinstance(self.log_toggle_button, wx.BitmapButton):
            self.log_toggle_button.SetBitmap(target_bmp_bundle)

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
            self.data_grid.DeleteRows(num_rows, current_grid_rows - num_rows)

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
        if self.main_panel_sizer and self.main_panel_sizer.GetItemCount() > 0:
            self.main_panel_sizer.Clear(True)
        self.webview = None
        self.back_button = None
        self.forward_button = None
        self.home_button = None
        self.data_grid = None
        self.view_mode_selector = None
        self.selected_row_index = None
        self.custom_highlighted_row_index = None
        self.open_action_button = None
        self.generate_action_button = None
        self.regenerate_action_button = None
        self.view_log_action_button = None
        self.delete_action_button = None
        self.log_text_ctrl = None
        self.log_toggle_button = None
        self.package_display_label = None

        self.splitter = None
        self.top_splitter_panel = None
        self.bottom_splitter_panel = None

        if self.panel:
            self.panel.Layout()
        if self.main_frame:
            self.main_frame.Layout()

    def _update_action_buttons_state(self) -> None:
        """Update state (enabled/disabled) of action buttons."""
        self.is_task_running = (
            self.generation_task_manager.has_any_active_tasks()
            if self.generation_task_manager
            else False
        )

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

        current_status = package_data.get("docset_status", "Not Available")
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
    app = DevilDexApp(core=core, initial_url="https://www.gazzetta.it")
    app.MainLoop()


if __name__ == "__main__":
    main()
