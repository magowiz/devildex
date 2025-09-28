"""test mcp integration."""

import asyncio
import socket
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import wx
from fastmcp import Client

from devildex.config_manager import ConfigManager
from devildex.core import DevilDexCore
from devildex.database import db_manager as database
from devildex.database.models import Docset, PackageInfo, RegisteredProject
from devildex.main import DevilDexApp

MIN_PORT_NUMBER = 1024
MAX_PORT_NUMBER = 65535


@pytest.fixture
def free_port() -> int:
    """Fixture to provide a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mock_config_manager(mocker: MagicMock, free_port: int) -> None:
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
def populated_db_session(tmp_path: Path) -> Generator[str, Any, None]:
    """Fixture to set up an in-memory SQLite database and populate it."""
    db_url = f"sqlite:///{tmp_path / 'test_db.db'}"
    database.init_db(db_url)

    with database.get_session() as session:
        project1 = RegisteredProject(
            project_name="TestProject",
            project_path="/path/to/test_project",
            python_executable="/path/to/python",
        )
        session.add(project1)
        session.commit()

        pkg_info_requests = PackageInfo(
            package_name="requests", summary="HTTP for Humans."
        )
        docset_requests = Docset(
            package_name="requests",
            package_version="2.25.1",
            status="available",
            package_info=pkg_info_requests,
        )
        session.add_all([pkg_info_requests, docset_requests])
        session.commit()
        project1.docsets.append(docset_requests)
        session.commit()

        pkg_info_flask = PackageInfo(package_name="flask", summary="Web framework.")
        docset_flask = Docset(
            package_name="flask",
            package_version="2.0.0",
            status="available",
            package_info=pkg_info_flask,
        )
        session.add_all([pkg_info_flask, docset_flask])
        session.commit()
        project1.docsets.append(docset_flask)
        session.commit()

        pkg_info_django = PackageInfo(package_name="django", summary="Web framework.")
        docset_django = Docset(
            package_name="django",
            package_version="3.2.0",
            status="available",
            package_info=pkg_info_django,
        )
        session.add_all([pkg_info_django, docset_django])
        session.commit()

    yield db_url
    database.DatabaseManager.close_db()
    (tmp_path / "test_db.db").unlink(missing_ok=True)


@pytest.fixture
def devildex_app_fixture(
    wx_app: wx.App,
    mock_config_manager: MagicMock,
    populated_db_session: str,
    mocker: MagicMock,
) -> Generator[DevilDexApp, Any, None]:
    """Fixture to create the main DevilDexApp instance for UI tests."""
    mocker.patch(
        "devildex.main.DevilDexCore.bootstrap_database_and_load_data", return_value=[]
    )
    mocker.patch("devildex.main.DevilDexCore.shutdown", return_value=None)

    core_instance = DevilDexCore(database_url=populated_db_session)

    main_app = DevilDexApp(core=core_instance)
    yield main_app
    if main_app.main_frame:
        wx.CallAfter(main_app.main_frame.Destroy)
    wx.Yield()


@pytest.mark.integration
def test_gui_only_no_mcp_starts(
    devildex_app_fixture: DevilDexApp, mock_config_manager: MagicMock, mocker: MagicMock
) -> None:
    """Verify that when MCP is disabled, the server process does not start."""
    mock_config_manager.get_mcp_server_enabled.return_value = False
    mock_config_manager.get_mcp_server_hide_gui_when_enabled.return_value = False

    devildex_app_fixture.OnInit()
    devildex_app_fixture._initialize_data_and_managers()

    assert devildex_app_fixture.core.mcp_server_manager is None
    assert devildex_app_fixture.main_frame is not None
    assert devildex_app_fixture.main_frame.IsShown()


@pytest.mark.asyncio
async def test_mcp_only_no_gui(
    free_port: int,
    tmp_path: Path,
    mcp_config_manager_for_test: ConfigManager, # Inject the new fixture
) -> None:
    """Test mcp only no gui."""
    test_name = "single_instance"
    mcp_port = free_port

    assert isinstance(mcp_port, int)
    assert MIN_PORT_NUMBER <= mcp_port <= MAX_PORT_NUMBER

    # Configure the mocked ConfigManager for this test
    mcp_config_manager_for_test.get_mcp_server_enabled.return_value = True
    mcp_config_manager_for_test.get_mcp_server_hide_gui_when_enabled.return_value = True
    mcp_config_manager_for_test.get_mcp_server_port.return_value = mcp_port

    # --- Step 3: Start the main application (DevilDexApp) ---
    app = wx.App(redirect=False)
    app.SetAppName(f"DevilDexTest_{test_name}")

    core_instance = (
        DevilDexCore()
    )  # Core will use ConfigManager, which uses ConfigManager, which uses our ENV var

    db_url_for_mcp = core_instance.database_url
    server_started = core_instance.start_mcp_server_if_enabled(db_url_for_mcp)
    assert server_started, "MCP server should have started"

    main_app = DevilDexApp(core=core_instance)

    main_app.OnInit()
    main_app._initialize_data_and_managers()
    assert (
        main_app.core is not None
    ), "main_app.core should not be None after initialization."

    assert (
        main_app.core.mcp_server_manager is not None
    ), "MCP server manager should be initialized."

    app_config = ConfigManager()

    assert (
        app_config.get_mcp_server_port() == mcp_port
    ), "App's ConfigManager should reflect the correct MCP port."

    assert (
        app_config.get_mcp_server_enabled() is True
    ), "App's ConfigManager should show MCP enabled."

    assert (
        app_config.get_mcp_server_hide_gui_when_enabled() is True
    ), "App's ConfigManager should show GUI hidden."

    # Assertion 3.4: Verify the GUI is hidden

    assert main_app.main_frame is not None, "Main frame should be created."

    assert not main_app.main_frame.IsShown(), "Main frame should be hidden."

    # --- Step 4: Test MCP client ---

    client_config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{mcp_port}/mcp"},
        }
    }
    client = Client(client_config, timeout=10)

    start_time = time.time()

    max_wait = 10  # seconds

    connected = False

    last_exception = None

    response = None

    while time.time() - start_time < max_wait:

        try:

            async with client:

                response = await client.call_tool(
                    "get_docsets_list", {"all_projects": True}
                )
            connected = True
            break
        except Exception as e:
            last_exception = e
            await asyncio.sleep(0.5)

    if not connected:

        raise AssertionError(
            f"Client could not connect to server within {max_wait} seconds. "
            f"Last exception: {last_exception}"
        )

    assert response is not None

    assert isinstance(response.data, list)

    # Sleep for a short time to ensure server is stable

    await asyncio.sleep(1)

    # --- Cleanup (will be moved to a finally block later) ---

    if main_app.main_frame:

        wx.CallAfter(main_app.main_frame.Destroy)

    main_app.OnExit()

@pytest.mark.mcp_config(enabled=True, hide_gui=False)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_gui_and_mcp_coexistence(
    devildex_app_fixture: DevilDexApp, mock_config_manager: MagicMock, mocker: MagicMock
) -> None:
    """Verify that GUI and MCP can coexist and function together."""
    mock_config_manager.get_mcp_server_enabled.return_value = True
    mock_config_manager.get_mcp_server_hide_gui_when_enabled.return_value = False
    mcp_port = mock_config_manager.get_mcp_server_port()

    devildex_app_fixture.OnInit()
    devildex_app_fixture._initialize_data_and_managers()

    db_url = devildex_app_fixture.core.database_url
    devildex_app_fixture.core.start_mcp_server_if_enabled(db_url)

    assert devildex_app_fixture.core.mcp_server_manager is not None
    assert devildex_app_fixture.core.mcp_server_manager.is_server_running()

    assert devildex_app_fixture.main_frame is not None
    assert devildex_app_fixture.main_frame.IsShown()

    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{mcp_port}/mcp"},
        }
    }
    client = Client(config, timeout=10)

    start_time = time.time()
    max_wait = 10  # seconds
    connected = False
    last_exception = None
    response = None

    while time.time() - start_time < max_wait:
        try:
            async with client:
                response = await client.call_tool(
                    "get_docsets_list", {"all_projects": True}
                )
            connected = True
            break
        except Exception as e:
            last_exception = e
            await asyncio.sleep(0.5)

    if not connected:
        pytest.fail(
            f"Client could not connect to server within {max_wait} seconds. "
            f"Last exception: {last_exception}"
        )

    assert response is not None
    assert isinstance(response.data, list)
    expected_names = [
        "requests",
        "flask",
        "django",
    ]
    assert sorted(response.data) == sorted(expected_names)
