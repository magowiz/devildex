"""docset database module."""
import datetime
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
    Column("project_id", Integer, ForeignKey("registered_project.id"), primary_key=True),
    Column("docset_id", Integer, ForeignKey("docset.id"), primary_key=True),
)
class DatabaseNotInitializedError(RuntimeError):
    """Raised when an operation is attempted before the database is initialized."""

    def __init__(self,
                 message: str = "Database not initialized. "
                                "Call init_db() first.") -> None:
        """Construct a new DatabaseNotInitializedError."""
        super().__init__(message)
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
    """Model for docset."""

    __tablename__ = "docset"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    package_name = Column(String, nullable=False, index=True)
    package_version = Column(String, nullable=False, index=True)
    index_file_name = Column(String, nullable=False, default="index.html")
    generation_timestamp_utc = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    status = Column(String, nullable=False, default="available")
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
        """Return il percorso del file database SQLite."""
        paths = AppPaths()
        _ = paths.user_data_dir
        return paths.database_path
    @classmethod
    def init_db(cls, database_url: Optional[str] = None) -> None:
        """Inizializza il motore del database e crea le tabelle se non exist."""
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
        """Return una nuova sessione del database.

        Assicura che init_db() sia stato chiamato.
        """
        if not cls._SessionLocal:
            logger.warning(
                "Attempting to get a DB session, but init_db() was not called. "
                "Initializing with default path."
            )
            cls.init_db()
            if not cls._SessionLocal:
                raise DatabaseNotInitializedError()

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s - %(name)s - %(funcName)s] %(message)s")
    logger.info("Initializing DB for standalone example...")
    # Per test, usiamo un database in memoria
    # init_db("sqlite:///:memory:")
    # Oppure, per testare il file su disco:
    db_file_for_test = Path("test_devildex_m2m.db")
    if db_file_for_test.exists():
        db_file_for_test.unlink()
    init_db(f"sqlite:///{db_file_for_test.resolve()}")


    logger.info("DB Initialized.")

    with get_session() as session:
        # Pulisci le tabelle (utile per riesecuzioni del test)
        session.execute(project_docset_association.delete()) # Pulisci prima la tabella di associazione
        session.query(Docset).delete()
        session.query(RegisteredProject).delete()
        session.commit()

        # Crea Progetti
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
        session.add_all([project1, project2])
        session.commit()
        logger.info(f"Added project: {project1}")
        logger.info(f"Added project: {project2}")

        # Crea Docsets
        # Nota: (package_name, package_version) deve essere unico per Docset
        docset_requests = Docset(
            package_name="requests", package_version="2.28.1", status="available"
        )
        docset_pandas = Docset(
            package_name="pandas", package_version="1.5.0", status="generating"
        )
        docset_flask = Docset(
            package_name="Flask", package_version="2.2.2", status="available"
        )
        session.add_all([docset_requests, docset_pandas, docset_flask])
        session.commit()
        logger.info(f"Added docset: {docset_requests}")
        logger.info(f"Added docset: {docset_pandas}")
        logger.info(f"Added docset: {docset_flask}")


        # Associa Docsets ai Progetti
        # Progetto WebApp usa requests e Flask
        project1.docsets.append(docset_requests)
        project1.docsets.append(docset_flask)

        # Progetto DataAnalysis usa requests e pandas
        project2.docsets.append(docset_requests) # requests è usato da entrambi
        project2.docsets.append(docset_pandas)

        session.commit()
        logger.info("Associations committed.")

        # Query di Esempio
        logger.info("-" * 20)
        retrieved_project1 = session.query(RegisteredProject).filter_by(project_name="WebAppProject").first()
        if retrieved_project1:
            logger.info(f"Docsets for {retrieved_project1.project_name}:")
            for ds in retrieved_project1.docsets:
                logger.info(f"  - {ds}")

        retrieved_project2 = session.query(RegisteredProject).filter_by(project_name="DataAnalysisProject").first()
        if retrieved_project2:
            logger.info(f"Docsets for {retrieved_project2.project_name}:")
            for ds in retrieved_project2.docsets:
                logger.info(f"  - {ds}")

        logger.info("-" * 20)
        retrieved_docset_requests = session.query(Docset).filter_by(package_name="requests").first()
        if retrieved_docset_requests:
            logger.info(f"Projects associated with {retrieved_docset_requests.package_name} "
                        f"v{retrieved_docset_requests.package_version}:")
            for proj in retrieved_docset_requests.associated_projects:
                logger.info(f"  - {proj.project_name}")

        all_docsets = session.query(Docset).all()
        logger.info("All docsets in DB and their associated projects:")
        for ds in all_docsets:
            project_names = ", ".join([p.project_name for p in ds.associated_projects])
            if not project_names:
                project_names = "None"
            logger.info(f"  - {ds} -> Projects: [{project_names}]")


    logger.info(f"Standalone example finished. Database file: {db_file_for_test.resolve() if db_file_for_test else 'in-memory'}")
