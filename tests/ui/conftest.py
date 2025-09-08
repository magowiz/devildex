"""Fixtures for UI tests."""

import pytest
import wx

from devildex.core import DevilDexCore
from devildex.main import DevilDexApp


@pytest.fixture
def core(populated_db_session) -> DevilDexCore:
    """Fixture to provide a DevilDexCore instance with a populated database."""
    # The database is already initialized by the populated_db_session fixture
    return DevilDexCore(database_url="sqlite:///:memory:")


@pytest.fixture
def devildex_app(wx_app: wx.App, core: DevilDexCore) -> DevilDexApp:
    """Fixture to create the main DevilDexApp instance."""
    app = DevilDexApp(core=core)
    app._initialize_data_and_managers()
    wx.Yield()  # Allow the UI to initialize
    yield app
    if app.main_frame:
        wx.CallAfter(app.main_frame.Destroy)
    wx.Yield()
