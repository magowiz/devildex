"""docset database module."""
import datetime
import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from devildex.app_paths import AppPaths

logger = logging.getLogger(__name__)

Base = declarative_base()

project_docset_association = Table(
    "project_docset_association",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("registered_project.id"),
           primary_key=True),
    Column("docset_id", Integer, ForeignKey("docset.id"), primary_key=True),
)


class DatabaseNotInitializedError(RuntimeError):
    """Raised when an operation is attempted before the database is initialized."""

    def __init__(self,
                 message: str = "Database not initialized. "
                                "Call init_db() first.") -> None:
        """Construct a new DatabaseNotInitializedError."""
        super().__init__(message)


class PackageInfo(Base): # type: ignore[valid-type,misc]
    """Model for general package information, common across versions."""

    __tablename__ = "package_info"

    package_name = Column(String, primary_key=True, index=True)
    summary = Column(Text, nullable=True)
    _project_urls_json = Column("project_urls", Text, nullable=True)

    docsets = relationship("Docset", back_populates="package_info")

    @property
    def project_urls(self) -> dict[str, str]:
        """Get project_urls come dictionary."""
        if self._project_urls_json:
            try:
                return json.loads(self._project_urls_json) # type: ignore[no-any-return]
            except json.JSONDecodeError:
                logger.exception(
                    "Error nel decoding project_urls JSON per package_info "
                    f"{self.package_name}: "
                    f"{self._project_urls_json}"
                )
                return {}
        return {}

    @project_urls.setter
    def project_urls(self, value: dict[str, str]) -> None:
        """Set up project_urls, converting it in JSON."""
        if value:
            self._project_urls_json = json.dumps(value)
        else:
            self._project_urls_json = None

    def __repr__(self) -> str:
        """Implement repr method."""
        return f"<PackageInfo(name='{self.package_name}')>"


class RegisteredProject(Base): # type: ignore[valid-type,misc]
    """Model for registered project."""

    __tablename__ = "registered_project"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_name = Column(String, unique=True, nullable=False, index=True)
    project_path = Column(String, unique=True, nullable=False)
    python_executable = Column(String, nullable=False, index=True)
    registration_timestamp_utc = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    docsets = relationship(
        "Docset",
        secondary=project_docset_association,
        back_populates="associated_projects",
    )

    def __repr__(self) -> str:
        """Implement repr method."""
        return (f"<RegisteredProject(id={self.id}, "
                f"name='{self.project_name}', python_exec='{self.python_executable}')>")


class Docset(Base): # type: ignore[valid-type,misc]
    """Model for docset, specific to a package version."""

    __tablename__ = "docset"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # package_name è ora una FK a PackageInfo.package_name
    package_name = Column(String, ForeignKey("package_info.package_name"),
                          nullable=False, index=True)
    package_version = Column(String, nullable=False, index=True)

    index_file_name = Column(String, nullable=False, default="index.html")
    generation_timestamp_utc = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    status = Column(String, nullable=False, default="unknown")

    package_info = relationship("PackageInfo", back_populates="docsets")

    associated_projects = relationship(
        "RegisteredProject",
        secondary=project_docset_association,
        back_populates="docsets",
    )

    __table_args__ = (
        UniqueConstraint(
            "package_name", "package_version", name="uq_docset_package_name_version"
        ),
    )

    def __repr__(self) -> str:
        """Implement repr method."""
        return (
            f"<Docset(id={self.id}, name='{self.package_name}', "
            f"version='{self.package_version}')>"
        )


class DatabaseManager:
    """Manages the database engine and session creation."""

    _engine: Optional[Engine] = None
    _SessionLocal: Optional[sessionmaker[SQLAlchemySession]] = None

    @staticmethod
    def get_db_path() -> Path:
        """Return il path del file database SQLite."""
        paths = AppPaths()
        _ = paths.user_data_dir
        return paths.database_path

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
        cls._SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls._engine
        )

        Base.metadata.create_all(bind=cls._engine)
        logger.info("Database tables checked/created.")

    @classmethod
    @contextmanager
    def get_session(cls) -> Generator[SQLAlchemySession, None, None]:
        """Return una new session del database.

        Ensures that init_db() was called.
        """
        if not cls._SessionLocal:
            logger.warning(
                "Attempting to get a DB session, but init_db() was not called. "
                "Initializing with default path."
            )
            cls.init_db()
            if not cls._SessionLocal:
                raise DatabaseNotInitializedError(
                    message="Failed to initialize SessionLocal even "
                    "after attempting default init."
                )

        db = cls._SessionLocal()
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
def ensure_package_entities_exist( # noqa: PLR0913
    session: SQLAlchemySession,
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
    """Ensure existence e links di PackageInfo, Docset e, RegisteredProject.

    - Crea PackageInfo se non exists per package_name.
    - Crea Docset se non exists per (package_name, package_version) e
        lo link a PackageInfo.
    - Se project_name is given:
        - Crea RegisteredProject se non exists.
        - Associate il Docset al RegisteredProject.

    Args:
        session: active session SQLAlchemy.
        package_name: Il nome del package.
        package_version: La version del package.
        summary: Summary del package (per creation PackageInfo).
        project_urls: URL del project (per creation PackageInfo).
        initial_docset_status: initial Status del Docset (per creation Docset).
        index_file_name: Nome del file index del Docset.
        project_name: (Optional) Nome del project.
        project_path: (Optional) Path del project
            (necessary se project_name è new).
        python_executable: (Optional) Executable Python
            (necessary se project_name è new).

    Returns:
        Una tuple (PackageInfo, Docset, Optional[RegisteredProject]).
        RegisteredProject object è None se project_name was not given.

    Raises:
        ValueError: Se project_name è given per un new project but
                    project_path o python_executable are missing.

    """
    pkg_info = session.query(PackageInfo).filter_by(package_name=package_name).first()
    if not pkg_info:
        logger.info(f"PackageInfo per '{package_name}' non trovato, creation...")
        pkg_info = PackageInfo(package_name=package_name, summary=summary)
        if project_urls:
            pkg_info.project_urls = project_urls
        session.add(pkg_info)
        logger.info(f"New PackageInfo '{package_name}' added alla session.")
    else:
        logger.debug(f"PackageInfo '{package_name}' trovato.")
        if summary and not pkg_info.summary:
            pkg_info.summary = summary
            logger.info(f"summary updated per PackageInfo '{package_name}'.")
        if project_urls and not pkg_info.project_urls:
            pkg_info.project_urls = project_urls
            logger.info(f"project_urls updated per PackageInfo '{package_name}'.")

    docset = (
        session.query(Docset)
        .filter_by(package_name=package_name, package_version=package_version)
        .first()
    )
    if not docset:
        logger.info(f"Docset per '{package_name} v{package_version}' "
                    "non trovato, creation...")
        docset = Docset(
            package_name=package_name, # FK
            package_version=package_version,
            status=initial_docset_status,
            index_file_name=index_file_name,
        )
        docset.package_info = pkg_info
        session.add(docset)
        logger.info(f"New Docset '{package_name} v{package_version}' "
                    "added and linked.")
    else:
        logger.debug(f"Docset '{package_name} v{package_version}' trovato.")

    registered_project_obj: Optional[RegisteredProject] = None
    if project_name:
        registered_project_obj = (
            session.query(RegisteredProject).filter_by(project_name=project_name).first()
        )
        if not registered_project_obj:
            logger.info(f"RegisteredProject '{project_name}' non trovato, creation...")
            if not project_path or not python_executable:
                msg = (
                    f"Per create un new RegisteredProject '{project_name}', "
                    "project_path e python_executable must be given."
                )
                logger.error(msg)
                raise ValueError(msg)
            registered_project_obj = RegisteredProject(
                project_name=project_name,
                project_path=str(project_path),
                python_executable=str(python_executable),
            )
            session.add(registered_project_obj)
            logger.info(f"New RegisteredProject '{project_name}' "
                        "added to session.")

        if docset not in registered_project_obj.docsets:
            registered_project_obj.docsets.append(docset)
            logger.info(
                f"Docset associated '{docset.package_name} v{docset.package_version}' "
                f"al project '{registered_project_obj.project_name}'."
            )
    return pkg_info, docset, registered_project_obj


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s - %(name)s - %(funcName)s] %(message)s")
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
                "Source": "https://github.com/psf/requests"
            }
        )
        pkg_info_pandas = PackageInfo(
            package_name="pandas",
            summary="Powerful data structures for data analysis, "
                    "time series, and statistics"
        )
        pkg_info_flask = PackageInfo(package_name="Flask")
        main_session.add_all([pkg_info_requests, pkg_info_pandas, pkg_info_flask])
        main_session.commit()
        logger.info(f"Added PackageInfo: {pkg_info_requests} with URLs: "
                    f"{pkg_info_requests.project_urls}")
        logger.info(f"Added PackageInfo: {pkg_info_pandas} with summary: "
                    f"{pkg_info_pandas.summary}")
        logger.info(f"Added PackageInfo: {pkg_info_flask}")

        docset_requests_v1 = Docset(
            package_info=pkg_info_requests,
            package_name="requests",
            package_version="2.28.1",
            status="available"
        )
        docset_requests_v2 = Docset(
            package_info=pkg_info_requests,
            package_name="requests",
            package_version="2.29.0",
            status="generating"
        )
        docset_pandas_v1 = Docset(
            package_info=pkg_info_pandas,
            package_name="pandas",
            package_version="1.5.0",
            status="available"
        )
        docset_flask_v1 = Docset(
            package_info=pkg_info_flask,
            package_name="Flask",
            package_version="2.2.2",
            status="error"
        )
        main_session.add_all([
            docset_requests_v1, docset_requests_v2, docset_pandas_v1, docset_flask_v1])
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
        retrieved_project1 = main_session.query(RegisteredProject).filter_by(
            project_name="WebAppProject").first()
        if retrieved_project1:
            logger.info(f"Docsets for {retrieved_project1.project_name}:")
            for ds in retrieved_project1.docsets:
                logger.info(f"  - {ds} (Info: {ds.package_info.summary[:30]
                if ds.package_info.summary else 'N/A'}...)")

        logger.info("-" * 20)
        retrieved_pkg_info_requests = main_session.query(PackageInfo).filter_by(
            package_name="requests").first()
        if retrieved_pkg_info_requests:
            logger.info("PackageInfo for "
                        f"'{retrieved_pkg_info_requests.package_name}':")
            logger.info(f"  Summary: {retrieved_pkg_info_requests.summary}")
            logger.info(f"  Project URLs: {retrieved_pkg_info_requests.project_urls}")
            logger.info("  Associated Docset versions:")
            for ds in retrieved_pkg_info_requests.docsets:
                logger.info(f"    - Version: {ds.package_version}, Status: {ds.status}")
                projects_using_this_version = ", ".join(
                    [p.project_name for p in ds.associated_projects])
                if not projects_using_this_version:
                    projects_using_this_version = "None"
                logger.info(f"      Used by projects: [{projects_using_this_version}]")

    logger.info("Standalone example finished. Database file: "
                f"{db_file_for_test.resolve()}")
