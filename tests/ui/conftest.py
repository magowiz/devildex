"""Fixtures for UI tests."""

from collections.abc import Generator

import pytest
import wx
from typing import Any
from pathlib import Path

from devildex.core import DevilDexCore
from devildex.main import DevilDexApp


@pytest.fixture
def wx_app() -> Generator[wx.App, None, None]:
    """Fixture to create a wx.App instance for each UI test."""
    app = wx.App()
    yield app
    app.Destroy()


@pytest.fixture
def core(populated_db_session: tuple[str, Any, str, Path, DevilDexCore]) -> DevilDexCore:
    """Fixture to provide a DevilDexCore instance with a populated database."""
    db_url, SessionLocal, project_name, temp_docset_path, _ = populated_db_session
    core_instance = DevilDexCore(database_url=db_url, docset_base_output_path=temp_docset_path)
    # Manually bootstrap the database and load data for the UI tests
    core_instance.bootstrap_database_and_load_data(initial_package_source=[], is_fallback_data=False)
    return core_instance


@pytest.fixture
def devildex_app(wx_app: wx.App, core: DevilDexCore) -> DevilDexApp:
    """Fixture to create the main DevilDexApp instance."""
    main_app = DevilDexApp(core=core)
    main_app._initialize_data_and_managers()
    wx.Yield()  # Allow the UI to initialize
    yield main_app
    if main_app.main_frame:
        wx.CallAfter(main_app.main_frame.Destroy)
    wx.Yield()
