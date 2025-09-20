"""conftest module."""

import logging
import os
import re
import socket
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import wx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from devildex.core import DevilDexCore
from devildex.database import db_manager
from devildex.database.models import Base, Docset, PackageInfo, RegisteredProject

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def free_port() -> int:
    """Fixture to provide a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session", autouse=True)
def aggregate_port_logs(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Session-scoped fixture to aggregate and print port logs from all workers."""
    # Create a truly shared temporary directory for all workers
    shared_tmp_dir = tmp_path_factory.mktemp("shared_port_logs")
    # Store its path in an environment variable for workers to access
    os.environ["PYTEST_SHARED_PORT_LOGS_DIR"] = str(shared_tmp_dir)

    central_log_paths_file = shared_tmp_dir / "all_port_log_paths.txt"

    yield  # Run tests first

    all_log_entries = []
    log_pattern = re.compile(r"(\d+\.\d+): (instance_\d+) \(PID (\d+)\) - (.+)")

    # Read all log file paths from the central file
    log_file_paths_to_read = []
    if central_log_paths_file.exists():
        with open(central_log_paths_file) as f:
            for line in f:
                log_file_paths_to_read.append(Path(line.strip()))

    for log_file_path in log_file_paths_to_read:
        try:
            with open(log_file_path) as f:
                for line in f:
                    match = log_pattern.match(line)
                    if match:
                        timestamp, test_name, pid, event = match.groups()
                        all_log_entries.append(
                            {
                                "timestamp": float(timestamp),
                                "test_name": test_name,
                                "pid": int(pid),
                                "event": event,
                                "raw_line": line.strip(),
                            }
                        )
        except FileNotFoundError:
            logger.warning(f"Log file not found: {log_file_path}")
        except Exception:
            logger.exception(f"Error reading log file {log_file_path}")

    # Sort all entries by timestamp
    all_log_entries.sort(key=lambda x: x["timestamp"])

    project_temp_dir = Path(os.getcwd()) / ".pytest_temp_logs"
    project_temp_dir.mkdir(exist_ok=True)
    final_aggregated_log_path = project_temp_dir / "aggregated_port_log.txt"

    with open(final_aggregated_log_path, "w") as outfile:
        outfile.write("---" + " Aggregated Chronological Port Log ---" + "\n")
        for entry in all_log_entries:
            outfile.write(
                f"{entry['timestamp']:.4f} | PID {entry['pid']} | "
                f"{entry['test_name']} | {entry['event']}\n"
            )
        outfile.write("---" + " End Aggregated Chronological Port Log ---" + "\n")

    logger.info(
        f"\nAggregated port log written to: {final_aggregated_log_path.resolve()}\n"
    )

    # Clean up the environment variable
    del os.environ["PYTEST_SHARED_PORT_LOGS_DIR"]


@pytest.fixture(scope="session")
def wx_app() -> wx.App:
    """Fixture to create a wx.App instance for the entire test session."""
    if not hasattr(wx, '_WX_APP_INSTANCE'):
        wx._WX_APP_INSTANCE = wx.App(redirect=False)
        wx._WX_APP_INSTANCE.SetAppName("DevilDexTest")
    return wx._WX_APP_INSTANCE


@pytest.fixture(scope="function")
def db_connection_and_tables() -> Generator[tuple[str, Any, Any], Any, None]:
    """Fixture to set up a temporary SQLite database and create tables."""
    with tempfile.TemporaryDirectory() as temp_db_dir:
        db_path = Path(temp_db_dir) / "test_db.sqlite"
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        try:
            yield db_url, engine, SessionLocal
        finally:
            engine.dispose()


@pytest.fixture(scope="function")
def populated_db_session(
    db_connection_and_tables: tuple[str, Any, Any],
) -> Generator[tuple[str, Any, str, Path, DevilDexCore], Any, None]:
    """Fixture to populate the database with test data."""
    db_url, engine, SessionLocal = db_connection_and_tables

    with tempfile.TemporaryDirectory() as temp_docset_dir:
        temp_docset_path = Path(temp_docset_dir)
        requests_docset_path = temp_docset_path / "requests" / "2.25.1"
        requests_docset_path.mkdir(parents=True, exist_ok=True)
        (requests_docset_path / "index.html").write_text("<h1>Requests Index</h1>")
        (requests_docset_path / "page1.html").write_text("<h2>Requests Page 1</h2>")
        (requests_docset_path / "subdir").mkdir(exist_ok=True)
        (requests_docset_path / "subdir" / "page2.html").write_text(
            "<h3>Requests Subdir Page 2</h3>"
        )

        core_instance = DevilDexCore(
            database_url=db_url, docset_base_output_path=temp_docset_path
        )

        pkg_info_requests = PackageInfo(
            package_name="requests", summary="HTTP for Humans."
        )
        docset_requests = Docset(
            package_name="requests",
            package_version="2.25.1",
            status="available",
            index_file_name="index.html",
            package_info=pkg_info_requests,
        )
        pkg_info_flask = PackageInfo(package_name="flask", summary="Web framework.")
        docset_flask = Docset(
            package_name="flask",
            package_version="2.0.0",
            status="available",
            index_file_name="index.html",
            package_info=pkg_info_flask,
        )
        pkg_info_django = PackageInfo(
            package_name="django", summary="Web framework."
        )
        docset_django = Docset(
            package_name="django",
            package_version="3.2.0",
            status="available",
            index_file_name="index.html",
            package_info=pkg_info_django,
        )
        pkg_info_numpy = PackageInfo(
            package_name="numpy", summary="Numerical computing."
        )
        docset_numpy = Docset(
            package_name="numpy",
            package_version="1.20.0",
            status="available",
            index_file_name="index.html",
            package_info=pkg_info_numpy,
        )
        pkg_info_pandas = PackageInfo(
            package_name="pandas", summary="Data analysis."
        )
        docset_pandas = Docset(
            package_name="pandas",
            package_version="1.3.0",
            status="available",
            index_file_name="index.html",
            package_info=pkg_info_pandas,
        )

        with SessionLocal() as session:
            project_name = f"TestProject_{uuid.uuid4()}"
            project1 = RegisteredProject(
                project_name=project_name,
                project_path=str(temp_docset_path),
                python_executable="/path/to/python",
            )
            session.add(project1)
            session.add_all(
                [
                    pkg_info_requests,
                    docset_requests,
                    pkg_info_flask,
                    docset_flask,
                    pkg_info_django,
                    docset_django,
                    pkg_info_numpy,
                    docset_numpy,
                    pkg_info_pandas,
                    docset_pandas,
                ]
            )
            project1.docsets.append(docset_requests)
            project1.docsets.append(docset_flask)
            session.commit()

        yield db_url, SessionLocal, project_name, temp_docset_path, core_instance
