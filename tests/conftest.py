"""Global fixtures for tests."""

import pytest
import wx
from sqlalchemy.orm import Session

from devildex import database


@pytest.fixture(scope="session")
def wx_app() -> wx.App:
    """Fixture to create a wx.App instance for the entire test session."""
    app = wx.App(redirect=False)
    app.SetAppName("DevilDexTest")
    return app


@pytest.fixture
def populated_db_session() -> Session:
    """
    Fixture to set up an in-memory SQLite database and populate it with test data.
    """
    db_url = "sqlite:///:memory:"
    database.init_db(db_url)
    try:
        with database.get_session() as session:
            database.ensure_package_entities_exist(
                package_name="requests",
                package_version="2.25.1",
                summary="HTTP for Humans.",
                project_urls={"Homepage": "https://requests.readthedocs.io"},
                project_name="TestProject",
                project_path="/path/to/project",
                python_executable="/path/to/python",
            )
            database.ensure_package_entities_exist(
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
        database.DatabaseManager.close_db()
