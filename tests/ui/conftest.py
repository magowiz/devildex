"""Fixtures for UI tests."""

from collections.abc import Generator

import pytest
import wx
from typing import Any
from pathlib import Path
import os

from devildex.core import DevilDexCore
from devildex.main import DevilDexApp
from devildex.database.models import PackageDetails


@pytest.fixture
def wx_app() -> Generator[wx.App, None, None]:
    """Fixture to create a wx.App instance for each UI test."""
    app = wx.App()
    yield app
    app.Destroy()


@pytest.fixture
def core(populated_db_session: tuple[str, Any, str, Path, DevilDexCore, list[PackageDetails]]) -> DevilDexCore:
    """Fixture to provide a DevilDexCore instance with a populated database."""
    db_url, SessionLocal, project_name, temp_docset_path, core_instance, initial_package_source = populated_db_session
    core_instance.bootstrap_database_and_load_data(initial_package_source=initial_package_source, is_fallback_data=False)
    return core_instance


@pytest.fixture
def devildex_app(wx_app: wx.App, core: DevilDexCore) -> DevilDexApp:
    """Fixture to create the main DevilDexApp instance."""
    main_app = DevilDexApp(core=core)
    os.environ["DEVILDEX_DB_PATH_OVERRIDE"] = core.database_url # Set env var for app
    main_app._initialize_data_and_managers()
    main_app.update_grid_data() # Explicitly update grid after initialization
    wx.Yield()  # Allow the UI to initialize
    try:
        yield main_app
    finally:
        if main_app.main_frame:
            wx.CallAfter(main_app.main_frame.Destroy)
        wx.Yield()
        del os.environ["DEVILDEX_DB_PATH_OVERRIDE"] # Clean up env var
