"""Fixtures for UI tests."""

from collections.abc import Generator

import pytest
import wx

from devildex.core import DevilDexCore
from devildex.main import DevilDexApp


@pytest.fixture(scope="session")
def wx_app() -> Generator[wx.App, None, None]:
    """Fixture to create a single wx.App instance for all UI tests."""
    app = wx.App()
    wx.App.SetInstance(app) # Add this line
    yield app
    app.Destroy()


@pytest.fixture
def core(populated_db_session: str) -> DevilDexCore:
    """Fixture to provide a DevilDexCore instance with a populated database."""
    return DevilDexCore(database_url="sqlite:///:memory:")


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
