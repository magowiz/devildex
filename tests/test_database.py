"""Tests for the database module."""

import pytest
from sqlalchemy.orm import Session

from devildex import database
from devildex.database import Docset, PackageInfo, RegisteredProject


@pytest.fixture
def db_session() -> Session:
    """Fixture to set up an in-memory SQLite database for testing.

    Yields a session to interact with the database.
    """
    db_url = "sqlite:///:memory:"
    database.init_db(db_url)
    try:
        with database.get_session() as session:
            yield session
    finally:
        # FIX: The DatabaseManager is a singleton-like class. Its state persists
        # between test runs, causing test contamination. We must explicitly
        # reset its engine and session factory after each test to ensure
        # that the next test gets a completely fresh in-memory database.
        database.DatabaseManager._engine = None
        database.DatabaseManager._session_local = None


def test_ensure_package_creates_new_records(db_session: Session) -> None:
    """Verify that new package, docset, and project records are created correctly."""
    # Arrange
    package_data = {
        "package_name": "requests",
        "package_version": "2.25.1",
        "summary": "HTTP for Humans.",
        "project_urls": {"Homepage": "https://requests.readthedocs.io"},
        "project_name": "TestProject",
        "project_path": "/path/to/project",
        "python_executable": "/path/to/python",
    }

    # Act
    database.ensure_package_entities_exist(**package_data)

    # Assert
    # Check PackageInfo
    pkg_info = (
        db_session.query(PackageInfo).filter_by(package_name="requests").one_or_none()
    )
    assert pkg_info is not None
    assert pkg_info.summary == "HTTP for Humans."
    assert pkg_info.project_urls["Homepage"] == "https://requests.readthedocs.io"

    # Check Docset
    docset = db_session.query(Docset).filter_by(package_name="requests").one_or_none()
    assert docset is not None
    assert docset.package_version == "2.25.1"
    assert docset.status == "unknown"
    assert docset.package_info == pkg_info

    # Check RegisteredProject
    project = (
        db_session.query(RegisteredProject)
        .filter_by(project_name="TestProject")
        .one_or_none()
    )
    assert project is not None
    assert project.project_path == "/path/to/project"
    assert project in docset.associated_projects


def test_ensure_package_updates_existing_records(db_session: Session) -> None:
    """Verify that existing records are updated correctly without duplicates."""
    # Arrange: First, create the initial records.
    initial_data = {
        "package_name": "pytest",
        "package_version": "6.2.0",  # Old version
        "summary": "testing framework",
        "project_urls": {},
    }
    database.ensure_package_entities_exist(**initial_data)

    # Act: Now, call the function again with updated data for the same package.
    updated_data = {
        "package_name": "pytest",
        "package_version": "7.0.0",  # New version
        "summary": "A better summary.",  # Updated summary
        "project_urls": {"Homepage": "https://pytest.org"},
    }
    database.ensure_package_entities_exist(**updated_data)

    # Assert
    # Ensure there is still only ONE PackageInfo record for pytest
    pkg_infos = db_session.query(PackageInfo).filter_by(package_name="pytest").all()
    assert len(pkg_infos) == 1
    # And that its summary has been updated
    assert pkg_infos[0].summary == "A better summary."
    assert pkg_infos[0].project_urls["Homepage"] == "https://pytest.org"

    # The function creates a new one for a new version. Let's test the new state.
    old_docset = (
        db_session.query(Docset)
        .filter_by(package_name="pytest", package_version="6.2.0")
        .one_or_none()
    )
    new_docset = (
        db_session.query(Docset)
        .filter_by(package_name="pytest", package_version="7.0.0")
        .one_or_none()
    )
    assert old_docset is not None  # The old one should still exist
    assert new_docset is not None  # The new one should have been created


def test_ensure_package_handles_no_project_context(db_session: Session) -> None:
    """Verify that the function works correctly when no project data is provided."""
    # Arrange
    package_data = {
        "package_name": "numpy",
        "package_version": "1.20.1",
        "summary": "Fundamental package for scientific computing",
        "project_urls": {},
        # No project_name, project_path, or python_executable
    }

    # Act
    database.ensure_package_entities_exist(**package_data)

    # Assert
    docset = db_session.query(Docset).filter_by(package_name="numpy").one_or_none()
    assert docset is not None
    assert not docset.associated_projects

    # Verify no project was created
    project_count = db_session.query(RegisteredProject).count()
    assert project_count == 0
