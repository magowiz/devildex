"""Tests for the database module."""

import pytest
import logging
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


def test_package_info_project_urls_setter_none_or_empty(db_session: Session) -> None:
    """Verify that setting project_urls to None or empty dict clears the JSON."""
    # Arrange: Create a PackageInfo with project_urls
    pkg_info = database.PackageInfo(
        package_name="test_pkg",
        summary="A test package",
        project_urls={"Homepage": "http://example.com"},
    )
    db_session.add(pkg_info)
    db_session.commit()
    db_session.refresh(pkg_info)

    assert pkg_info._project_urls_json is not None

    # Act: Set project_urls to None
    pkg_info.project_urls = None
    db_session.commit()
    db_session.refresh(pkg_info)
    assert pkg_info._project_urls_json is None

    # Act: Set project_urls to an empty dict
    pkg_info.project_urls = {}
    db_session.commit()
    db_session.refresh(pkg_info)
    assert pkg_info._project_urls_json is None


def test_database_manager_init_db_called_twice(caplog, mocker) -> None:
    """Verify that calling init_db twice logs a debug message and doesn't re-initialize."""
    # Arrange
    database.DatabaseManager._engine = None  # Ensure clean state
    database.DatabaseManager._session_local = None

    # Act 1: First call to init_db
    mocker.patch("devildex.database.logger.info")
    database.init_db("sqlite:///:memory:")
    database.logger.info.assert_any_call("Initializing database at: sqlite:///:memory:")
    database.logger.info.assert_any_call("Database tables checked/created.")

    # Act 2: Second call to init_db
    database.logger.info.reset_mock() # Reset mock calls for the second check
    mocker.patch("devildex.database.logger.debug")
    database.init_db("sqlite:///:memory:")
    database.logger.debug.assert_any_call("Database engine already initialized.")

    # Assert that no re-initialization happened (e.g., no new tables created log)
    database.logger.info.assert_not_called()


def test_get_docsets_for_project_view_sqlalchemy_error(mocker, caplog) -> None:
    """Verify get_docsets_for_project_view handles SQLAlchemyError."""
    # Arrange
    mocker.patch(
        "devildex.database.DatabaseManager.execute_statement",
        side_effect=database.SQLAlchemyError("Test DB Error"),
    )
    # Ensure get_session yields a mock session that doesn't raise an error on close
    mock_session = mocker.MagicMock(spec=database.SQLAlchemySession)
    mocker.patch("devildex.database.get_session", return_value=mock_session)

    # Act
    with caplog.at_level(logging.ERROR):
        result = database.DatabaseManager.get_docsets_for_project_view(None)

    # Assert
    assert result == []
    assert "Error retrieving docsets for the view" in caplog.text


def test_get_all_registered_projects_details_sqlalchemy_error(mocker, caplog) -> None:
    """Verify get_all_registered_projects_details handles SQLAlchemyError."""
    # Arrange
    mocker.patch(
        "devildex.database.DatabaseManager.execute_statement",
        side_effect=database.SQLAlchemyError("Test DB Error"),
    )
    mock_session = mocker.MagicMock(spec=database.SQLAlchemySession)
    mocker.patch("devildex.database.get_session", return_value=mock_session)

    # Act
    with caplog.at_level(logging.ERROR):
        result = database.DatabaseManager.get_all_registered_projects_details()

    # Assert
    assert result == []
    assert "Error retrieving all registered projects" in caplog.text


def test_get_project_details_by_name_not_found(db_session: Session, caplog) -> None:
    """Verify get_project_details_by_name returns None and logs warning for non-existent project."""
    # Arrange
    non_existent_project = "NonExistentProject"

    # Act
    with caplog.at_level(logging.WARNING):
        result = database.DatabaseManager.get_project_details_by_name(
            non_existent_project
        )

    # Assert
    assert result is None
    assert (
        f"No project found in the DB with name '{non_existent_project}'." in caplog.text
    )


def test_get_project_details_by_name_sqlalchemy_error(mocker, caplog) -> None:
    """Verify get_project_details_by_name handles SQLAlchemyError."""
    # Arrange
    mocker.patch(
        "devildex.database.DatabaseManager.execute_statement",
        side_effect=database.SQLAlchemyError("Test DB Error"),
    )
    mock_session = mocker.MagicMock(spec=database.SQLAlchemySession)
    mocker.patch("devildex.database.get_session", return_value=mock_session)

    # Act
    with caplog.at_level(logging.ERROR):
        result = database.DatabaseManager.get_project_details_by_name("AnyProject")

    # Assert
    assert result is None
    assert "Error retrieving details for project 'AnyProject'" in caplog.text


def test_get_session_raises_database_not_initialized_error(mocker, caplog) -> None:
    """Verify get_session raises DatabaseNotInitializedError if init_db fails."""
    # Arrange
    database.DatabaseManager._session_local = None  # Ensure it's not initialized
    # Mock init_db to not set _session_local, simulating a failure
    mocker.patch(
        "devildex.database.DatabaseManager.init_db",
        side_effect=lambda *args, **kwargs: None,
    )

    # Act & Assert
    with pytest.raises(database.DatabaseNotInitializedError) as excinfo:
        with database.DatabaseManager.get_session():
            pass
    assert "Failed to initialize SessionLocal even after attempting default init." in str(excinfo.value)


def test_get_session_logs_warning_if_not_initialized(mocker, caplog) -> None:
    """Verify get_session logs a warning if init_db was not called."""
    # Arrange
    database.DatabaseManager._session_local = None  # Ensure it's not initialized
    # Mock init_db to actually initialize the session, but we still expect the warning
    mocker.patch(
        "devildex.database.DatabaseManager.init_db",
        side_effect=lambda *args, **kwargs: (
            setattr(database.DatabaseManager, "_session_local", mocker.MagicMock())
        ),
    )

    # Act
    with caplog.at_level(logging.WARNING):
        with database.DatabaseManager.get_session():
            pass

    # Assert
    assert (
        "Attempting to get a DB session, but init_db() was not called." in caplog.text
    )


def test_ensure_registered_project_and_association_value_error(db_session: Session, caplog) -> None:
    """Verify _ensure_registered_project_and_association raises ValueError for missing project details."""
    # Arrange
    pkg_info = database.PackageInfo(package_name="test_pkg")
    docset = database.Docset(package_name="test_pkg", package_version="1.0", status="unknown")
    db_session.add_all([pkg_info, docset])
    db_session.commit()

    # Act & Assert
    with pytest.raises(ValueError) as excinfo:
        database._ensure_registered_project_and_association(
            db_session,
            project_name="NewProject",
            project_path=None,  # Missing
            python_executable="/path/to/python",
            docset=docset,
        )
    assert "project_path and python_executable must be provided." in str(excinfo.value)
    assert "To create a new RegisteredProject 'NewProject', project_path and python_executable must be provided." in caplog.text


def test_ensure_package_entities_exist_commit_exception(mocker, caplog) -> None:
    """Verify ensure_package_entities_exist handles commit exceptions."""
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

    # Mock database.get_session to return a mock context manager
    mock_context_manager = mocker.MagicMock()
    mock_session = mocker.MagicMock(spec=database.SQLAlchemySession)
    mock_session.commit.side_effect = database.SQLAlchemyError("Commit failed")
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_session.query.return_value.filter_by.return_value.one_or_none.return_value = None

    mock_context_manager.__enter__.return_value = mock_session
    mocker.patch("devildex.database.get_session", return_value=mock_context_manager)

    # Act & Assert
    with pytest.raises(database.SQLAlchemyError) as excinfo:
        with caplog.at_level(logging.ERROR):
            database.ensure_package_entities_exist(**package_data)

    assert "Commit failed" in str(excinfo.value)
    assert "Error during final commit while ensuring package entities." in caplog.text
    mock_session.rollback.assert_called_once()



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
