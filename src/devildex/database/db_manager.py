"""docset database module."""

import logging
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Engine,
    Executable,
    Result,
    create_engine,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import selectinload, sessionmaker

from devildex.app_paths import AppPaths

from .models import (
    Docset,
    PackageInfo,
    RegisteredProject,
    project_docset_association,
)

logger = logging.getLogger(__name__)


def get_base_path() -> Path:
    """Get the base path for resources, whether running as script or bundled."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    else:
        return Path(__file__).parent.parent


class DatabaseNotInitializedError(RuntimeError):
    """Raised when an operation is attempted before the database is initialized."""

    def __init__(
        self, message: str = "Database not initialized. Call init_db() first."
    ) -> None:
        """Construct a new DatabaseNotInitializedError."""
        super().__init__(message)


class DatabaseManager:
    """Manages the database engine and session creation."""

    _engine: Optional[Engine] = None
    _session_local: Optional[sessionmaker[SQLAlchemySession]] = None

    @staticmethod
    def get_db_path() -> Path:
        """Return il path del file database SQLite."""
        paths = AppPaths()
        _ = paths.user_data_dir
        return paths.database_path

    @classmethod
    def execute_statement(
        cls, statement: Executable, session: SQLAlchemySession
    ) -> Result:
        """Execute a given SQLAlchemy statement on the provided session.

        Args:
            session: The active SQLAlchemy session.
            statement: The SQLAlchemy statement to execute (e.g., created with select(),
                       update(), delete(), insert()).

        Returns:
            A SQLAlchemy Result object that can be used to fetch data
            (e.g., result.scalars().all(), result.scalar_one_or_none(),
            result.rowcount).

        """
        logger.debug(f"Executing statement: {statement}")
        return session.execute(statement)

    @classmethod
    def get_all_project_names(cls) -> list[str]:
        """Retrieve only the NAMES of all registered projects, sorted.

        Returns a list of strings.
        """
        project_names_list: list[str]
        stmt = select(RegisteredProject.project_name).order_by(
            RegisteredProject.project_name
        )
        with get_session() as session:
            result = cls.execute_statement(stmt, session)
            project_names_list = cast(list[str], result.scalars().all())
            logger.info(
                f"Retrieved {len(project_names_list)} registered project names "
                "from the DB."
            )
        return project_names_list

    @classmethod
    def get_docsets_for_project_view(
        cls, project_name_filter: Optional[str]
    ) -> list[dict[str, Any]]:
        """Retrieve docsets formatted for the grid view.

        Includes the associated project name, if present.
        Filters by project if project_name_filter is provided.
        """
        grid_data_to_return: list[dict[str, Any]] = []

        stmt = select(Docset).options(
            selectinload(Docset.package_info),
            selectinload(Docset.associated_projects),
        )

        if project_name_filter:
            stmt = stmt.join(Docset.associated_projects).where(
                RegisteredProject.project_name == project_name_filter
            )

        stmt = stmt.order_by(Docset.package_name, Docset.package_version)

        try:
            with get_session() as session:
                result = cls.execute_statement(stmt, session)
                docsets_from_db = result.scalars().unique().all()

                for db_docset in docsets_from_db:
                    pkg_info = db_docset.package_info

                    associated_project_name_for_display: Optional[str] = None
                    if db_docset.associated_projects:
                        associated_project_name_for_display = (
                            db_docset.associated_projects[0].project_name
                        )

                    grid_row = {
                        "id": db_docset.id,
                        "name": db_docset.package_name,
                        "version": db_docset.package_version,
                        "description": (
                            pkg_info.summary if pkg_info and pkg_info.summary else "N/A"
                        ),
                        "docset_status": db_docset.status,
                        "project_name": associated_project_name_for_display,
                    }
                    if pkg_info and pkg_info.project_urls:
                        grid_row["project_urls"] = pkg_info.project_urls
                    grid_data_to_return.append(grid_row)

                view_type = (
                    f"project '{project_name_filter}'"
                    if project_name_filter
                    else "global"
                )
                logger.info(
                    f"Retrieved {len(grid_data_to_return)} docset(s) "
                    f"for the {view_type} view."
                )
        except SQLAlchemyError:
            logger.exception("Error retrieving docsets for the view")
            return []
        return grid_data_to_return

    @classmethod
    def get_all_registered_projects_details(cls) -> list[dict[str, Any]]:
        """Get registered project details."""
        projects_list: list[dict[str, Any]] = []
        stmt = select(RegisteredProject).order_by(RegisteredProject.project_name)
        try:
            with get_session() as session:
                result = cls.execute_statement(stmt, session)
                for db_project in result.scalars().all():
                    projects_list.append(
                        {
                            "project_name": db_project.project_name,
                            "project_path": db_project.project_path,
                            "python_executable": db_project.python_executable,
                        }
                    )
                logger.info(
                    f"Retrieved {len(projects_list)} registered projects from the DB."
                )
        except SQLAlchemyError:
            logger.exception("Error retrieving all registered projects")
            return []
        return projects_list

    @classmethod
    def init_db(cls, database_url: Optional[str] = None) -> None:
        """Initialize il engine del database e crea le tables se non exist."""
        if cls._engine:
            logger.debug("Database engine already initialized.")
            return

        if not database_url:
            db_path = cls.get_db_path()
            database_url = f"sqlite:///{db_path.resolve()}"

        logger.info(f"Initializing database at: {database_url}")

        cls._engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        cls._session_local = sessionmaker(
            autocommit=False, autoflush=False, bind=cls._engine
        )

        if not os.environ.get("DEVILDEX_TESTING"):
            try:
                logger.info("Checking for database migrations...")

                base_path = Path(get_base_path())
                if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                    # PyInstaller bundle paths
                    alembic_ini_path = base_path / "devildex" / "alembic.ini"
                    alembic_script_location = base_path / "devildex" / "alembic"
                else:
                    # Development environment paths
                    alembic_ini_path = Path(__file__).parent.parent / "alembic.ini"
                    alembic_script_location = Path(__file__).parent.parent / "alembic"

                alembic_cfg = Config(str(alembic_ini_path))
                alembic_cfg.set_main_option(
                    "script_location", str(alembic_script_location)
                )

                command.upgrade(alembic_cfg, "head")
                logger.info(
                    "--- DIRECT PRINT: DATABASE MIGRATION COMPLETED."
                    " APPLICATION CONTINUES. ---",
                )
            except Exception:
                logger.exception("Failed to run database migrations.")

    @classmethod
    def get_project_details_by_name(
        cls, project_name_to_find: str
    ) -> Optional[dict[str, Any]]:
        """Retrieve the complete details of a project specified by name."""
        stmt = select(RegisteredProject).where(
            RegisteredProject.project_name == project_name_to_find
        )
        try:
            with get_session() as session:
                result = cls.execute_statement(stmt, session)
                db_project = result.scalar_one_or_none()
                if db_project:
                    logger.info(
                        f"Details retrieved for project '{project_name_to_find}'."
                    )
                    return {
                        "project_name": db_project.project_name,
                        "project_path": db_project.project_path,
                        "python_executable": db_project.python_executable,
                    }
                logger.warning(
                    f"No project found in the DB with name '{project_name_to_find}'."
                )
                return None
        except SQLAlchemyError:
            logger.exception(
                f"Error retrieving details for project '{project_name_to_find}'"
            )
            return None

    @classmethod
    def close_db(cls) -> None:
        """Close the database engine."""
        if cls._engine:
            cls._engine.dispose()
            cls._engine = None
            cls._session_local = None
            logger.info("Database engine disposed.")

    @classmethod
    @contextmanager
    def get_session(cls) -> Generator[SQLAlchemySession, None, None]:
        """Return una new session del database.

        Ensures that init_db() was called.
        """
        if not cls._session_local:
            logger.warning(
                "Attempting to get a DB session, but init_db() was not called. "
                "Initializing with default path."
            )
            cls.init_db()
            if not cls._session_local:
                raise DatabaseNotInitializedError(
                    message="Failed to initialize SessionLocal even "
                    "after attempting default init."
                )

        db = cls._session_local()
        try:
            yield db
        finally:
            db.close()


def init_db(database_url: Optional[str] = None) -> None:
    """Initialize the database through the DatabaseManager."""
    DatabaseManager.init_db(database_url)


@contextmanager
def get_session() -> Generator[SQLAlchemySession, None, None]:
    """Provide a db session through the DatabaseManager using a context manager."""
    with DatabaseManager.get_session() as db_session:
        yield db_session


def _ensure_package_info(
    session: SQLAlchemySession,
    package_name: str,
    summary: Optional[str],
    project_urls: Optional[dict[str, str]],
) -> PackageInfo:
    """Get or creates a PackageInfo entity."""
    pkg_info = session.query(PackageInfo).filter_by(package_name=package_name).first()
    if not pkg_info:
        logger.info(f"PackageInfo for '{package_name}' not found, creating...")
        pkg_info = PackageInfo(package_name=package_name, summary=summary)
        if project_urls:
            pkg_info.project_urls = project_urls
        session.add(pkg_info)
        logger.info(f"New PackageInfo '{package_name}' added to session.")
    else:
        logger.debug(f"PackageInfo '{package_name}' found.")
        if summary:
            pkg_info.summary = summary
            logger.info(f"Summary updated for PackageInfo '{package_name}'.")
        if project_urls:
            pkg_info.project_urls = project_urls
            logger.info(f"Project URLs updated for PackageInfo '{package_name}'.")
    return pkg_info


def _ensure_docset(
    session: SQLAlchemySession,
    pkg_info: PackageInfo,
    package_version: str,
    initial_docset_status: str,
    index_file_name: str,
) -> Docset:
    """Get or creates a Docset entity and links it to PackageInfo."""
    package_name = pkg_info.package_name
    docset = (
        session.query(Docset)
        .filter_by(package_name=package_name, package_version=package_version)
        .first()
    )
    if not docset:
        logger.info(
            f"Docset for '{package_name} v{package_version}' not found, creating..."
        )
        docset = Docset(
            package_name=package_name,
            package_version=package_version,
            status=initial_docset_status,
            index_file_name=index_file_name,
            package_info=pkg_info,
        )
        session.add(docset)
        logger.info(f"New Docset '{package_name} v{package_version}' added and linked.")
    return docset


def _ensure_registered_project_and_association(
    session: SQLAlchemySession,
    project_name: Optional[str],
    project_path: Optional[str],
    python_executable: Optional[str],
    docset: Docset,
) -> Optional[RegisteredProject]:
    """Get or creates a RegisteredProject and associates it with the given Docset.

    Returns None if project_name is not provided.
    """
    if not project_name:
        return None

    registered_project_obj = (
        session.query(RegisteredProject).filter_by(project_name=project_name).first()
    )
    if not registered_project_obj:
        logger.info(f"RegisteredProject '{project_name}' not found, creating...")
        if not project_path or not python_executable:
            msg = (
                f"To create a new RegisteredProject '{project_name}', "
                "project_path and python_executable must be provided."
            )
            logger.error(msg)
            raise ValueError(msg)
        registered_project_obj = RegisteredProject(
            project_name=project_name,
            project_path=str(project_path),
            python_executable=str(python_executable),
        )
        session.add(registered_project_obj)
        logger.info(f"New RegisteredProject '{project_name}' added to session.")

    if docset not in registered_project_obj.docsets:
        registered_project_obj.docsets.append(docset)
        logger.info(
            f"Docset '{docset.package_name} v{docset.package_version}' "
            f"associated with project '{registered_project_obj.project_name}'."
        )
    return registered_project_obj


def ensure_package_entities_exist(  # noqa: PLR0913
    package_name: str,
    package_version: str,
    summary: Optional[str] = None,
    project_urls: Optional[dict[str, str]] = None,
    initial_docset_status: str = "unknown",
    index_file_name: str = "index.html",
    project_name: Optional[str] = None,
    project_path: Optional[str] = None,
    python_executable: Optional[str] = None,
) -> tuple[PackageInfo, Docset, Optional[RegisteredProject]]:
    """Ensure PackageInfo, Docset, and optionally RegisteredProject entities.

    - Creates PackageInfo if it doesn't exist for the given package_name.
    - Creates Docset if it doesn't exist for the
        (package_name, package_version) pair and links it to PackageInfo.
    - If project_name is provided:
        - Creates RegisteredProject if it doesn't exist.
        - Associates the Docset with the RegisteredProject.

    Args:
        package_name: The name of the package.
        package_version: The version of the package.
        summary: Summary of the package (for PackageInfo creation).
        project_urls: Project URLs (for PackageInfo creation).
        initial_docset_status: Initial status of the Docset (for Docset creation).
        index_file_name: Name of the Docset's index file.
        project_name: (Optional) Name of the project.
        project_path: (Optional) Path of the project (required if
            project_name is for a new project).
        python_executable: (Optional) Python executable path (required if
            project_name is for a new project).

    Returns:
        A tuple (PackageInfo, Docset, Optional[RegisteredProject]).
        The RegisteredProject object is None if project_name was not provided.

    Raises:
        ValueError: If project_name is provided for a new project but
                    project_path or python_executable are missing.

    """
    with get_session() as session:
        pkg_info = _ensure_package_info(session, package_name, summary, project_urls)
        docset = _ensure_docset(
            session,
            pkg_info,
            package_version,
            initial_docset_status,
            index_file_name,
        )
        registered_project_obj = _ensure_registered_project_and_association(
            session, project_name, project_path, python_executable, docset
        )

        try:
            session.commit()
            log_message = (
                "Successfully ensured entities for package "
                f"'{package_name} v{package_version}'"
            )
            if project_name:
                log_message += f" and project '{project_name}'"
            log_message += "."
            logger.info(log_message)
        except Exception:
            logger.exception(
                "Error during final commit while ensuring package entities."
            )
            session.rollback()
            raise
    return pkg_info, docset, registered_project_obj


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s - %(name)s - %(funcName)s] %(message)s",
    )
    logger.info("Initializing DB for standalone example...")
    db_file_for_test = Path("test_devildex_pkginfo.db")
    if db_file_for_test.exists():
        db_file_for_test.unlink()
    init_db(f"sqlite:///{db_file_for_test.resolve()}")
    logger.info("DB Initialized.")

    with get_session() as main_session:
        main_session.execute(project_docset_association.delete())
        main_session.query(Docset).delete()
        main_session.query(PackageInfo).delete()
        main_session.query(RegisteredProject).delete()
        main_session.commit()

        project1 = RegisteredProject(
            project_name="WebAppProject",
            project_path="/path/to/webapp",
            python_executable="/path/to/webapp/.venv/bin/python",
        )
        project2 = RegisteredProject(
            project_name="DataAnalysisProject",
            project_path="/path/to/dataanalysis",
            python_executable="/path/to/dataanalysis/.venv/bin/python",
        )
        main_session.add_all([project1, project2])
        main_session.commit()

        pkg_info_requests = PackageInfo(
            package_name="requests",
            summary="Elegant and simple HTTP library for Python, built "
            "for human beings.",
            project_urls={
                "Homepage": "https://requests.readthedocs.io/",
                "Documentation": "https://requests.readthedocs.io/en/latest/",
                "Source": "https://github.com/psf/requests",
            },
        )
        pkg_info_pandas = PackageInfo(
            package_name="pandas",
            summary="Powerful data structures for data analysis, "
            "time series, and statistics",
        )
        pkg_info_flask = PackageInfo(package_name="Flask")
        main_session.add_all([pkg_info_requests, pkg_info_pandas, pkg_info_flask])
        main_session.commit()
        logger.info(
            f"Added PackageInfo: {pkg_info_requests} with URLs: "
            f"{pkg_info_requests.project_urls}"
        )
        logger.info(
            f"Added PackageInfo: {pkg_info_pandas} with summary: "
            f"{pkg_info_pandas.summary}"
        )
        logger.info(f"Added PackageInfo: {pkg_info_flask}")

        docset_requests_v1 = Docset(
            package_info=pkg_info_requests,
            package_name="requests",
            package_version="2.28.1",
            status="available",
        )
        docset_requests_v2 = Docset(
            package_info=pkg_info_requests,
            package_name="requests",
            package_version="2.29.0",
            status="generating",
        )
        docset_pandas_v1 = Docset(
            package_info=pkg_info_pandas,
            package_name="pandas",
            package_version="1.5.0",
            status="available",
        )
        docset_flask_v1 = Docset(
            package_info=pkg_info_flask,
            package_name="Flask",
            package_version="2.2.2",
            status="error",
        )
        main_session.add_all(
            [docset_requests_v1, docset_requests_v2, docset_pandas_v1, docset_flask_v1]
        )
        main_session.commit()
        logger.info(f"Added Docset: {docset_requests_v1}")
        logger.info(f"Added Docset: {docset_requests_v2}")
        logger.info(f"Added Docset: {docset_pandas_v1}")
        logger.info(f"Added Docset: {docset_flask_v1}")

        project1.docsets.append(docset_requests_v1)
        project1.docsets.append(docset_flask_v1)
        project2.docsets.append(docset_requests_v2)
        project2.docsets.append(docset_pandas_v1)
        main_session.commit()

        logger.info("-" * 20)
        retrieved_project1 = (
            main_session.query(RegisteredProject)
            .filter_by(project_name="WebAppProject")
            .first()
        )
        if retrieved_project1:
            logger.info(f"Docsets for {retrieved_project1.project_name}:")
            for ds in retrieved_project1.docsets:
                logger.info(
                    f"  - {ds} (Info: "
                    f"{ds.package_info.summary[:30]
                    if ds.package_info.summary else 'N/A'}...)"
                )

        logger.info("-" * 20)
        retrieved_pkg_info_requests = (
            main_session.query(PackageInfo).filter_by(package_name="requests").first()
        )
        if retrieved_pkg_info_requests:
            logger.info(
                "PackageInfo for " f"'{retrieved_pkg_info_requests.package_name}':"
            )
            logger.info(f"  Summary: {retrieved_pkg_info_requests.summary}")
            logger.info(f"  Project URLs: {retrieved_pkg_info_requests.project_urls}")
            logger.info("  Associated Docset versions:")
            for ds in retrieved_pkg_info_requests.docsets:
                logger.info(f"    - Version: {ds.package_version}, Status: {ds.status}")
                projects_using_this_version = ", ".join(
                    [p.project_name for p in ds.associated_projects]
                )
                if not projects_using_this_version:
                    projects_using_this_version = "None"
                logger.info(f"      Used by projects: [{projects_using_this_version}]")

    logger.info(
        "Standalone example finished. Database file: " f"{db_file_for_test.resolve()}"
    )
