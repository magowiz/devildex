"""Global fixtures for tests."""

import pytest
import wx
from sqlalchemy.orm import Session

from devildex.database import db_manager


_WX_APP_INSTANCE = None

@pytest.fixture(scope="session")
def wx_app() -> wx.App:
    """Fixture to create a wx.App instance for the entire test session (once per worker)."""
    global _WX_APP_INSTANCE
    if _WX_APP_INSTANCE is None:
        _WX_APP_INSTANCE = wx.App(redirect=False)
        _WX_APP_INSTANCE.SetAppName("DevilDexTest")
    return _WX_APP_INSTANCE


@pytest.fixture
def populated_db_session() -> Session:
    """
    Fixture to set up an in-memory SQLite database and populate it with test data.
    """
    db_url = "sqlite:///:memory:"
    db_manager.init_db(db_url)
    try:
        with db_manager.get_session() as session:
            db_manager.ensure_package_entities_exist(
                package_name="requests",
                package_version="2.25.1",
                summary="HTTP for Humans.",
                project_urls={"Homepage": "https://requests.readthedocs.io"},
                project_name="TestProject",
                project_path="/path/to/project",
                python_executable="/path/to/python",
            )
            db_manager.ensure_package_entities_exist(
                package_name="pytest",
                package_version="7.0.0",
                summary="A better summary.",
                project_urls={"Homepage": "https://pytest.org"},
                project_name="TestProject",
                project_path="/path/to/project",
                python_executable="/path/to/python",
            )
            yield session
    finally:
        db_manager.DatabaseManager.close_db()
