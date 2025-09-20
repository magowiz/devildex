"""conftest module."""

import logging
import os
import re
import socket
from collections.abc import Generator
from pathlib import Path

import pytest
import wx
from sqlalchemy.orm import Session

from devildex.database import db_manager

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


@pytest.fixture
def populated_db_session() -> Generator[Session, None, None]:
    """Fixture to set up an in-memory SQLite database and populate it with test data."""
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
                project_path="/tmp/test_project",
                python_executable="/usr/bin/python3",
            )
            db_manager.ensure_package_entities_exist(
                package_name="pytest",
                package_version="7.0.0",
                summary="A better summary.",
                project_urls={"Homepage": "https://pytest.org"},
                project_name="TestProject",
                project_path="/tmp/test_project",
                python_executable="/usr/bin/python3",
            )
            yield session
    finally:
        db_manager.DatabaseManager.close_db()
