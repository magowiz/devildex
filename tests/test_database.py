"""Tests for the database module."""


import pytest
from pytest_mock import MockerFixture
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from devildex.database import db_manager as database
from devildex.database.models import Base, Docset, PackageInfo, RegisteredProject

LEN_DATA = 2


@pytest.fixture
def db_session() -> Session | None:
    """Fixture to set up an in-memory SQLite database for testing.

    Yields a session to interact with the database.
    """
    db_url = "sqlite:///:memory:"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    database.DatabaseManager._engine = engine
    database.DatabaseManager._session_local = session_local

    try:
        with session_local() as session:
            yield session
    finally:
        database.DatabaseManager.close_db()


def test_ensure_package_creates_new_records(db_session: Session) -> None:
    """Verify that new package, docset, and project records are created correctly."""
    package_data = {
        "package_name": "requests",
        "package_version": "2.25.1",
        "summary": "HTTP for Humans.",
        "project_urls": {"Homepage": "https://requests.readthedocs.io"},
        "project_name": "TestProject",
        "project_path": "/path/to/project",
        "python_executable": "/path/to/python",
    }
    database.ensure_package_entities_exist(**package_data)
    pkg_info = (
        db_session.query(PackageInfo).filter_by(package_name="requests").one_or_none()
    )
    assert pkg_info is not None
    assert pkg_info.summary == "HTTP for Humans."
    assert pkg_info.project_urls["Homepage"] == "https://requests.readthedocs.io"
    docset = db_session.query(Docset).filter_by(package_name="requests").one_or_none()
    assert docset is not None
    assert docset.package_version == "2.25.1"
    assert docset.status == "unknown"
    assert docset.package_info == pkg_info
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
    initial_data = {
        "package_name": "pytest",
        "package_version": "6.2.0",
        "summary": "testing framework",
        "project_urls": {},
    }
    database.ensure_package_entities_exist(**initial_data)
    updated_data = {
        "package_name": "pytest",
        "package_version": "7.0.0",
        "summary": "A better summary.",
        "project_urls": {"Homepage": "https://pytest.org"},
    }
    database.ensure_package_entities_exist(**updated_data)
    pkg_infos = db_session.query(PackageInfo).filter_by(package_name="pytest").all()
    assert len(pkg_infos) == 1
    assert pkg_infos[0].summary == "A better summary."
    assert pkg_infos[0].project_urls["Homepage"] == "https://pytest.org"


def test_package_info_project_urls_setter_none_or_empty(db_session: Session) -> None:
    """Verify that setting project_urls to None or empty dict clears the JSON."""
    pkg_info = database.PackageInfo(
        package_name="test_pkg",
        summary="A test package",
        project_urls={"Homepage": "http://example.com"},
    )
    db_session.add(pkg_info)
    db_session.commit()
    db_session.refresh(pkg_info)
    assert pkg_info._project_urls_json is not None
    pkg_info.project_urls = None
    db_session.commit()
    db_session.refresh(pkg_info)
    assert pkg_info._project_urls_json is None
    pkg_info.project_urls = {}
    db_session.commit()
    db_session.refresh(pkg_info)
    assert pkg_info._project_urls_json is None


def test_database_manager_init_db_called_twice(
    mocker: MockerFixture
) -> None:
    """Verify calling init_db twice logs a debug message and doesn't re-initialize."""
    database.DatabaseManager._engine = None
    database.DatabaseManager._session_local = None
    mock_logger_info = mocker.patch("devildex.database.db_manager.logger.info")
    database.init_db("sqlite:///:memory:")
    mock_logger_info.assert_any_call("Initializing database at: sqlite:///:memory:")
    mock_logger_info.reset_mock()
    mock_logger_debug = mocker.patch("devildex.database.db_manager.logger.debug")
    database.init_db("sqlite:///:memory:")
    mock_logger_debug.assert_any_call("Database engine already initialized.")
    mock_logger_info.assert_not_called()


def test_get_docsets_for_project_view_sqlalchemy_error(
    mocker: MockerFixture
) -> None:
    """Verify get_docsets_for_project_view handles SQLAlchemyError."""
    mocker.patch(
        "devildex.database.db_manager.DatabaseManager.execute_statement",
        side_effect=database.SQLAlchemyError("Test DB Error"),
    )
    mock_session = mocker.MagicMock(spec=database.SQLAlchemySession)
    mocker.patch("devildex.database.db_manager.get_session", return_value=mock_session)
    mock_logger = mocker.patch("devildex.database.db_manager.logger")
    result = database.DatabaseManager.get_docsets_for_project_view(None)
    assert result == []
    mock_logger.exception.assert_called_once_with("Error retrieving docsets for the view")


def test_get_all_registered_projects_details_sqlalchemy_error(
    mocker: MockerFixture
) -> None:
    """Verify get_all_registered_projects_details handles SQLAlchemyError."""
    mocker.patch(
        "devildex.database.db_manager.DatabaseManager.execute_statement",
        side_effect=database.SQLAlchemyError("Test DB Error"),
    )
    mock_session = mocker.MagicMock(spec=database.SQLAlchemySession)
    mocker.patch("devildex.database.db_manager.get_session", return_value=mock_session)
    mock_logger = mocker.patch("devildex.database.db_manager.logger")
    result = database.DatabaseManager.get_all_registered_projects_details()
    assert result == []
    mock_logger.exception.assert_called_once_with("Error retrieving all registered projects")


def test_get_project_details_by_name_not_found(
    db_session: Session, mocker: MockerFixture
) -> None:
    """Verify get_project_details_by_name returns None, logs warning for no proj."""
    non_existent_project = "NonExistentProject"
    mock_logger = mocker.patch("devildex.database.db_manager.logger")
    result = database.DatabaseManager.get_project_details_by_name(
        non_existent_project
    )
    assert result is None
    mock_logger.warning.assert_called_once_with(
        f"No project found in the DB with name '{non_existent_project}'."
    )


def test_get_project_details_by_name_sqlalchemy_error(
    mocker: MockerFixture
) -> None:
    """Verify get_project_details_by_name handles SQLAlchemyError."""
    mocker.patch(
        "devildex.database.db_manager.DatabaseManager.execute_statement",
        side_effect=database.SQLAlchemyError("Test DB Error"),
    )
    mock_session = mocker.MagicMock(spec=database.SQLAlchemySession)
    mocker.patch("devildex.database.db_manager.get_session", return_value=mock_session)
    mock_logger = mocker.patch("devildex.database.db_manager.logger")
    result = database.DatabaseManager.get_project_details_by_name("AnyProject")
    assert result is None
    mock_logger.exception.assert_called_once_with(
        "Error retrieving details for project 'AnyProject'"
    )


def test_get_session_raises_database_not_initialized_error(
    mocker: MockerFixture
) -> None:
    """Verify get_session raises DatabaseNotInitializedError if init_db fails."""
    database.DatabaseManager._session_local = None
    mocker.patch(
        "devildex.database.db_manager.DatabaseManager.init_db",
        side_effect=lambda *args, **kwargs: None,
    )
    with pytest.raises(database.DatabaseNotInitializedError) as excinfo:
        with database.DatabaseManager.get_session():
            pass
    assert (
        "Failed to initialize SessionLocal even after attempting default init."
        in str(excinfo.value)
    )


def test_get_session_logs_warning_if_not_initialized(
    mocker: MockerFixture
) -> None:
    """Verify get_session logs a warning if init_db was not called."""
    database.DatabaseManager._session_local = None
    mocker.patch(
        "devildex.database.db_manager.DatabaseManager.init_db",
        side_effect=lambda *args, **kwargs: (
            setattr(database.DatabaseManager, "_session_local", mocker.MagicMock())
        ),
    )
    mock_logger = mocker.patch("devildex.database.db_manager.logger")
    with database.DatabaseManager.get_session():
        pass

    mock_logger.warning.assert_called_once_with(
        "Attempting to get a DB session, but init_db() was not called. "
        "Initializing with default path."
    )


def test_ensure_registered_project_and_association_value_error(
    db_session: Session, mocker: MockerFixture
) -> None:
    """Check ens reg proj and association raise ValueError if no proj details."""
    pkg_info = database.PackageInfo(package_name="test_pkg")
    docset = database.Docset(
        package_name="test_pkg", package_version="1.0", status="unknown"
    )
    db_session.add_all([pkg_info, docset])
    db_session.commit()

    mock_logger = mocker.patch("devildex.database.db_manager.logger")
    with pytest.raises(
        ValueError,
        match=r"project_path and python_executable must be provided.",
    ) as excinfo:
        database._ensure_registered_project_and_association(
            db_session,
            project_name="NewProject",
            project_path=None,
            python_executable="/path/to/python",
            docset=docset,
        )
    assert "project_path and python_executable must be provided." in str(excinfo.value)
    mock_logger.error.assert_called_once_with(
        "To create a new RegisteredProject 'NewProject', project_path and "
        "python_executable must be provided."
    )


def test_ensure_package_entities_exist_commit_exception(
    mocker: MockerFixture
) -> None:
    """Verify ensure_package_entities_exist handles commit exceptions."""
    package_data = {
        "package_name": "requests",
        "package_version": "2.25.1",
        "summary": "HTTP for Humans.",
        "project_urls": {"Homepage": "https://requests.readthedocs.io"},
        "project_name": "TestProject",
        "project_path": "/path/to/project",
        "python_executable": "/path/to/python",
    }
    mock_context_manager = mocker.MagicMock()
    mock_session = mocker.MagicMock(spec=database.SQLAlchemySession)
    mock_session.commit.side_effect = database.SQLAlchemyError("Commit failed")
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_session.query.return_value.filter_by.return_value.one_or_none.return_value = (
        None
    )

    mock_context_manager.__enter__.return_value = mock_session
    mocker.patch(
        "devildex.database.db_manager.get_session", return_value=mock_context_manager
    )

    mock_logger = mocker.patch("devildex.database.db_manager.logger")

    with pytest.raises(database.SQLAlchemyError) as excinfo:
        database.ensure_package_entities_exist(**package_data)

    assert "Commit failed" in str(excinfo.value)
    mock_logger.exception.assert_called_once_with(
        "Error during final commit while ensuring package entities."
    )
    mock_session.rollback.assert_called_once()


def test_ensure_package_handles_no_project_context(db_session: Session) -> None:
    """Verify that the function works correctly when no project data is provided."""
    package_data = {
        "package_name": "numpy",
        "package_version": "1.20.1",
        "summary": "Fundamental package for scientific computing",
        "project_urls": {},
    }
    database.ensure_package_entities_exist(**package_data)
    docset = db_session.query(Docset).filter_by(package_name="numpy").one_or_none()
    assert docset is not None
    assert not docset.associated_projects
    project_count = db_session.query(RegisteredProject).count()
    assert project_count == 0


def test_package_info_repr(db_session: Session) -> None:
    """Verify the __repr__ method of the PackageInfo model."""
    pkg_info = database.PackageInfo(package_name="test_package")
    db_session.add(pkg_info)
    db_session.commit()
    repr_string = repr(pkg_info)
    assert repr_string == "<PackageInfo(name='test_package')>"


def test_registered_project_repr(db_session: Session) -> None:
    """Verify the __repr__ method of the RegisteredProject model."""
    project = database.RegisteredProject(
        project_name="TestProject",
        project_path="/path/to/project",
        python_executable="/usr/bin/python",
    )
    db_session.add(project)
    db_session.commit()
    repr_string = repr(project)
    assert (
        repr_string == f"<RegisteredProject(id={project.id}, "
        "name='TestProject', python_exec='/usr/bin/python')>"
    )


def test_docset_repr(db_session: Session) -> None:
    """Verify the __repr__ method of the Docset model."""
    pkg_info = database.PackageInfo(package_name="test_package")
    db_session.add(pkg_info)
    db_session.commit()
    docset = database.Docset(
        package_name="test_package", package_version="1.0.0", package_info=pkg_info
    )
    db_session.add(docset)
    db_session.commit()
    repr_string = repr(docset)
    assert (
        repr_string == f"<Docset(id={docset.id}, name='test_package', version='1.0.0')>"
    )


def test_database_not_initialized_error_default_message() -> None:
    """Verify the default message of the DatabaseNotInitializedError."""
    error = database.DatabaseNotInitializedError()
    assert str(error) == "Database not initialized. Call init_db() first."


def test_database_not_initialized_error_custom_message() -> None:
    """Verify the custom message of the DatabaseNotInitializedError."""
    custom_message = "The database is offline."
    error = database.DatabaseNotInitializedError(message=custom_message)
    assert str(error) == custom_message


def test_package_info_project_urls_json_decode_error(
    db_session: Session, mocker: MockerFixture
) -> None:
    """Verify that a JSONDecodeError is handled when accessing project_urls."""
    invalid_json = '{"key": "value"'
    pkg_info = database.PackageInfo(
        package_name="invalid_json_pkg", _project_urls_json=invalid_json
    )
    db_session.add(pkg_info)
    db_session.commit()
    mock_logger = mocker.MagicMock()
    mocker.patch("logging.getLogger", return_value=mock_logger)
    urls = pkg_info.project_urls
    assert urls == {}
    assert mock_logger.exception.call_args[0][0].startswith("Error nel decoding project_urls JSON per package_info")


def test_get_all_project_names(db_session: Session) -> None:
    """Verify that get_all_project_names returns a sorted list of project names."""
    project1 = RegisteredProject(
        project_name="ProjectB",
        project_path="/path/b",
        python_executable="/py/b",
    )
    project2 = RegisteredProject(
        project_name="ProjectA",
        project_path="/path/a",
        python_executable="/py/a",
    )
    db_session.add_all([project1, project2])
    db_session.commit()
    project_names = database.DatabaseManager.get_all_project_names()
    assert project_names == ["ProjectA", "ProjectB"]


def test_get_docsets_for_project_view_with_filter(db_session: Session) -> None:
    """Verify get_docsets_for_project_view filters correctly by project name."""
    proj1_data = {
        "package_name": "PackageA",
        "package_version": "1.0",
        "project_name": "Project1",
        "project_path": "/path/1",
        "python_executable": "/py/1",
        "summary": "Summary A",
    }
    database.ensure_package_entities_exist(**proj1_data)
    proj2_data = {
        "package_name": "PackageB",
        "package_version": "1.0",
        "project_name": "Project2",
        "project_path": "/path/2",
        "python_executable": "/py/2",
        "summary": "Summary B",
    }
    database.ensure_package_entities_exist(**proj2_data)
    view_data = database.DatabaseManager.get_docsets_for_project_view("Project1")
    assert len(view_data) == 1
    assert view_data[0]["name"] == "PackageA"
    assert view_data[0]["project_name"] == "Project1"


def test_get_docsets_for_project_view_no_filter(db_session: Session) -> None:
    """Verify get_docsets_for_project_view returns all docsets if no filter applied."""
    proj1_data = {
        "package_name": "PackageA",
        "package_version": "1.0",
        "project_name": "Project1",
        "project_path": "/path/1",
        "python_executable": "/py/1",
    }
    database.ensure_package_entities_exist(**proj1_data)
    proj2_data = {
        "package_name": "PackageB",
        "package_version": "1.0",
        "project_name": "Project2",
        "project_path": "/path/2",
        "python_executable": "/py/2",
    }
    database.ensure_package_entities_exist(**proj2_data)
    view_data = database.DatabaseManager.get_docsets_for_project_view(None)
    assert len(view_data) == LEN_DATA
    package_names = sorted([d["name"] for d in view_data])
    assert package_names == ["PackageA", "PackageB"]


def test_get_docsets_for_project_view_no_summary_or_urls(db_session: Session) -> None:
    """Verify the view handles docsets with no summary or project URLs gracefully."""
    pkg_info = PackageInfo(package_name="minimal_pkg")
    docset = Docset(
        package_name="minimal_pkg", package_version="1.0", package_info=pkg_info
    )
    db_session.add_all([pkg_info, docset])
    db_session.commit()
    view_data = database.DatabaseManager.get_docsets_for_project_view(None)
    assert len(view_data) == 1
    assert view_data[0]["name"] == "minimal_pkg"
    assert view_data[0]["description"] == "N/A"
    assert "project_urls" not in view_data[0]
    assert view_data[0]["project_name"] is None


def test_get_db_path(mocker: MockerFixture) -> str:
    """Verify that the get_db_path method returns the correct path."""
    mock_app_paths = mocker.patch("devildex.database.db_manager.AppPaths").return_value
    mock_app_paths.database_path = "/fake/path/devildex.db"
    db_path = database.DatabaseManager.get_db_path()
    assert db_path == "/fake/path/devildex.db"


def test_ensure_docset_creates_new(db_session: Session) -> None:
    """Verify that _ensure_docset creates a new docset if it doesn't exist."""
    pkg_info = PackageInfo(package_name="test-pkg")
    db_session.add(pkg_info)
    db_session.commit()

    docset = database._ensure_docset(
        session=db_session,
        pkg_info=pkg_info,
        package_version="1.0.0",
        initial_docset_status="pending",
        index_file_name="overview.html",
    )
    db_session.commit()

    assert docset.package_name == "test-pkg"
    assert docset.package_version == "1.0.0"
    assert docset.status == "pending"
    assert docset.index_file_name == "overview.html"
    assert docset.package_info == pkg_info


def test_ensure_registered_project_and_association_associates_existing_project(
    db_session: Session,
) -> None:
    """Verify that an existing project is correctly associated with a docset."""
    project = RegisteredProject(
        project_name="ExistingProject",
        project_path="/path/exist",
        python_executable="/py/exist",
    )
    pkg_info = PackageInfo(package_name="any-pkg")
    docset = Docset(
        package_name="any-pkg", package_version="1.0", package_info=pkg_info
    )
    db_session.add_all([project, pkg_info, docset])
    db_session.commit()
    database._ensure_registered_project_and_association(
        session=db_session,
        project_name="ExistingProject",
        project_path=None,
        python_executable=None,
        docset=docset,
    )
    db_session.commit()
    db_session.refresh(project)
    db_session.refresh(docset)
    assert docset in project.docsets


def test_ensure_package_entities_exist_no_project_name(db_session: Session) -> None:
    """Verify that no RegisteredProject is created when project_name is None."""
    package_data = {
        "package_name": "no-project-pkg",
        "package_version": "1.0",
        "project_name": None,
    }
    _, _, registered_project = database.ensure_package_entities_exist(**package_data)
    assert registered_project is None
    project_count = db_session.query(RegisteredProject).count()
    assert project_count == 0
