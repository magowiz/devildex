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
    create_engine,
)
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from devildex.app_paths import AppPaths

logger = logging.getLogger(__name__)

Base = declarative_base()
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
    docsets = relationship("Docset", back_populates="associated_project")

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
    registered_project_id = Column(Integer, ForeignKey("registered_project.id"),
                                   nullable=True, index=True)
    associated_project = relationship("RegisteredProject", back_populates="docsets")

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
        if cls._engine:  # Access via cls
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

        Base.metadata.create_all(bind=cls._engine)  # Use the class's engine
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
    init_db()

    logger.info("DB Initialized.")

    with get_session() as session:
        session.query(Docset).delete()
        session.query(RegisteredProject).delete()
        session.commit()

        new_project = RegisteredProject(
            project_name="MyDevProject",
            project_path="/path/to/mydevproject",
            python_executable="/path/to/mydevproject/.venv/bin/python",
        )
        session.add(new_project)
        session.commit()
        session.refresh(new_project)
        logger.info(f"Added project: {new_project}")

        generic_docset = Docset(
            package_name="requests",
            package_version="2.28.1",
            index_file_name="index.html",
            status="available"
        )
        session.add(generic_docset)
        session.commit()
        session.refresh(generic_docset)
        logger.info(f"Added generic docset: {generic_docset}")

        project_specific_docset = Docset(
            package_name="MyDevProjectInternalLib",
            package_version="0.1.0",
            index_file_name="main.html",
            status="available",
            associated_project=new_project
        )
        session.add(project_specific_docset)
        session.commit()
        session.refresh(project_specific_docset)
        logger.info(f"Added project-specific docset: {project_specific_docset}")

        # Query
        retrieved_project = session.query(
            RegisteredProject).filter_by(project_name="MyDevProject").first()
        if retrieved_project:
            logger.info(f"Retrieved project: {retrieved_project}")
            logger.info(f"Docsets for {retrieved_project.project_name}:")
            for ds in retrieved_project.docsets:
                logger.info(f"  - {ds}")

        all_docsets = session.query(Docset).all()
        logger.info("All docsets in DB:")
        for ds in all_docsets:
            logger.info(f"  - {ds} (Project ID: {ds.registered_project_id})")

    logger.info("Standalone example finished.")
