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
from unittest.mock import MagicMock

import pytest
import wx
from pytest_mock import MockerFixture
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from devildex.config_manager import ConfigManager
from devildex.constants import (
    AVAILABLE_BTN_LABEL,
)
from devildex.core import DevilDexCore
from devildex.database.models import (
    Base,
    Docset,
    PackageDetails,
    PackageInfo,
    RegisteredProject,
)
from devildex.main import DevilDexApp

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def configure_logging():
    logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(scope="session")
def free_port() -> int:
    """Fixture to provide a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mock_config_manager(mocker: MockerFixture, free_port: int) -> None:
    """Fixture to mock the ConfigManager singleton for test control."""
    ConfigManager._instance = None
    mocker.patch("devildex.config_manager.ConfigManager._initialize", return_value=None)
    mocker.patch(
        "devildex.config_manager.ConfigManager._load_config", return_value=None
    )
    mocker.patch("devildex.config_manager.ConfigManager.save_config", return_value=None)

    mock_instance = ConfigManager()
    mocker.patch("devildex.config_manager.ConfigManager", return_value=mock_instance)
    mocker.patch("devildex.config_manager.ConfigManager._instance", new=mock_instance)

    mock_instance.get_mcp_server_enabled = mocker.Mock(return_value=False)
    mock_instance.get_mcp_server_hide_gui_when_enabled = mocker.Mock(return_value=False)
    mock_instance.get_mcp_server_port = mocker.Mock(return_value=free_port)

    return mock_instance


@pytest.fixture
def mcp_config_manager_for_test(mocker: MockerFixture) -> ConfigManager:
    """Fixture to provide a configurable ConfigManager for MCP tests."""
    ConfigManager._instance = None
    mocker.patch(
        "devildex.config_manager.ConfigManager._load_config", return_value=None
    )

    config_manager = ConfigManager()

    config_manager.get_mcp_server_enabled = mocker.Mock(return_value=False)
    config_manager.get_mcp_server_hide_gui_when_enabled = mocker.Mock(
        return_value=False
    )
    config_manager.get_mcp_server_port = mocker.Mock(return_value=8001)

    return config_manager


@pytest.fixture
def devildex_app_fixture(
    wx_app: wx.App,
    mock_config_manager: MagicMock,
    populated_db_session: tuple[
        str, Any, str, Path, DevilDexCore, list[PackageDetails]
    ],
    mocker: MockerFixture,
) -> Generator[DevilDexApp, Any, None]:
    """Fixture to create the main DevilDexApp instance for UI tests."""
    mocker.patch(
        "devildex.main.DevilDexCore.bootstrap_database_and_load_data", return_value=[]
    )
    mocker.patch("devildex.main.DevilDexCore.shutdown", return_value=None)

    core_instance = DevilDexCore(database_url=populated_db_session[0])

    main_app = DevilDexApp(core=core_instance)
    yield main_app
    if main_app.main_frame:
        wx.CallAfter(main_app.main_frame.Destroy)
    wx.Yield()


@pytest.fixture(scope="session", autouse=True)
def aggregate_port_logs(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Session-scoped fixture to aggregate and print port logs from all workers."""
    shared_tmp_dir = tmp_path_factory.mktemp("shared_port_logs")
    os.environ["PYTEST_SHARED_PORT_LOGS_DIR"] = str(shared_tmp_dir)
    central_log_paths_file = shared_tmp_dir / "all_port_log_paths.txt"
    yield

    all_log_entries = []
    log_pattern = re.compile(r"(\d+\.\d+): (instance_\d+) \(PID (\d+)\) - (.+)")
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
    del os.environ["PYTEST_SHARED_PORT_LOGS_DIR"]


@pytest.fixture(scope="session")
def wx_app() -> wx.App:
    """Fixture to create a wx.App instance for the entire test session."""
    if not hasattr(wx, "_WX_APP_INSTANCE"):
        wx._WX_APP_INSTANCE = wx.App(redirect=False)
        wx._WX_APP_INSTANCE.SetAppName("DevilDexTest")
    return wx._WX_APP_INSTANCE


@pytest.fixture
def db_connection_and_tables() -> Generator[tuple[str, Any, Any], Any, None]:
    """Fixture to set up a temporary SQLite database and create tables."""
    os.environ["DEVILDEX_TESTING"] = "1"
    try:
        with tempfile.TemporaryDirectory() as temp_db_dir:
            db_path = Path(temp_db_dir) / "test_db.sqlite"
            db_url = f"sqlite:///{db_path}"
            engine = create_engine(db_url)
            Base.metadata.create_all(engine)
            session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            try:
                yield db_url, engine, session_local
            finally:
                engine.dispose()
    finally:
        del os.environ["DEVILDEX_TESTING"]


@pytest.fixture
def populated_db_session(
    db_connection_and_tables: tuple[str, Any, Any],
    default_docset_status: str = AVAILABLE_BTN_LABEL,
) -> Generator[
    tuple[str, Any, str, Path, DevilDexCore, list[PackageDetails]], Any, None
]:
    """Fixture to populate the database with test data."""
    db_url, _engine, session_local = db_connection_and_tables
    os.environ["DEVILDEX_CUSTOM_DB_PATH"] = db_url.replace("sqlite:////", "")

    with tempfile.TemporaryDirectory() as temp_docset_dir:
        temp_docset_path = Path(temp_docset_dir)
        create_disk_files = default_docset_status == "available"

        if create_disk_files:
            docset_names_versions = {
                "requests": "2.25.1",
                "flask": "2.0.0",
                "django": "3.2.0",
                "numpy": "1.20.0",
                "pandas": "1.3.0",
            }
            for name, version in docset_names_versions.items():
                docset_path = temp_docset_path / name / version
                docset_path.mkdir(parents=True, exist_ok=True)
                (docset_path / "index.html").write_text(
                    f"<h1>{name} {version} Index</h1>"
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
            status=default_docset_status,
            index_file_name="index.html" if create_disk_files else None,
            package_info=pkg_info_requests,
        )
        pkg_info_flask = PackageInfo(package_name="flask", summary="Web framework.")
        docset_flask = Docset(
            package_name="flask",
            package_version="2.0.0",
            status=default_docset_status,
            index_file_name="index.html" if create_disk_files else None,
            package_info=pkg_info_flask,
        )
        pkg_info_django = PackageInfo(package_name="django", summary="Web framework.")
        docset_django = Docset(
            package_name="django",
            package_version="3.2.0",
            status=default_docset_status,
            index_file_name="index.html" if create_disk_files else None,
            package_info=pkg_info_django,
        )
        pkg_info_numpy = PackageInfo(
            package_name="numpy", summary="Numerical computing."
        )
        docset_numpy = Docset(
            package_name="numpy",
            package_version="1.20.0",
            status=default_docset_status,
            index_file_name="index.html" if create_disk_files else None,
            package_info=pkg_info_numpy,
        )
        pkg_info_pandas = PackageInfo(package_name="pandas", summary="Data analysis.")
        docset_pandas = Docset(
            package_name="pandas",
            package_version="1.3.0",
            status=default_docset_status,
            index_file_name="index.html" if create_disk_files else None,
            package_info=pkg_info_pandas,
        )

        with session_local() as session:
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

        yield db_url, session_local, project_name, temp_docset_path, core_instance, [
            PackageDetails(
                name="requests", version="2.25.1", status=default_docset_status
            ),
            PackageDetails(name="flask", version="2.0.0", status=default_docset_status),
            PackageDetails(
                name="django", version="3.2.0", status=default_docset_status
            ),
            PackageDetails(
                name="numpy", version="1.20.0", status=default_docset_status
            ),
            PackageDetails(
                name="pandas", version="1.3.0", status=default_docset_status
            ),
        ]