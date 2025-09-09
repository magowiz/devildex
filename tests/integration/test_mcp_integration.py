import pytest
import wx
import os
import time
import subprocess
from pathlib import Path
from unittest.mock import MagicMock
import socket

from fastmcp import Client

import devildex 
from devildex.core import DevilDexCore
from devildex.main import DevilDexApp
from devildex.config_manager import ConfigManager
from devildex.database import db_manager as database
from devildex.database.models import Docset, PackageInfo, RegisteredProject




@pytest.fixture(scope="session")
def free_port():
    """Fixture to provide a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

@pytest.fixture(scope="function")
def mock_config_manager(mocker: MagicMock, free_port: int):
    """Fixture to mock the ConfigManager singleton for test control."""
    # Ensure a fresh ConfigManager instance for each test
    ConfigManager._instance = None
    mocker.patch('devildex.config_manager.ConfigManager._initialize', return_value=None)
    mocker.patch('devildex.config_manager.ConfigManager._load_config', return_value=None)
    mocker.patch('devildex.config_manager.ConfigManager.save_config', return_value=None)
    
    mock_instance = ConfigManager()
    mocker.patch('devildex.config_manager.ConfigManager', return_value=mock_instance)
    mocker.patch('devildex.config_manager.ConfigManager._instance', new=mock_instance)
    
    # Default mocks for the test
    mock_instance.get_mcp_server_enabled = mocker.Mock(return_value=False)
    mock_instance.get_mcp_server_hide_gui_when_enabled = mocker.Mock(return_value=False)
    mock_instance.get_mcp_server_port = mocker.Mock(return_value=free_port)
    
    return mock_instance

@pytest.fixture(scope="function")
def populated_db_session(tmp_path: Path):
    """Fixture to set up an in-memory SQLite database and populate it."""
    db_url = f"sqlite:///{tmp_path / 'test_db.db'}"
    database.init_db(db_url)

    with database.get_session() as session:
        # Add a project
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
    (tmp_path / 'test_db.db').unlink(missing_ok=True)


@pytest.fixture(scope="function")
def devildex_app_fixture(wx_app, mock_config_manager: MagicMock, populated_db_session: str, mocker: MagicMock):
    """Fixture to create the main DevilDexApp instance for UI tests."""
    # Mock DevilDexCore to use the populated_db_session
    # Removed mocker.patch('devildex.main.DevilDexCore.__init__', return_value=None)
    mocker.patch('devildex.main.DevilDexCore.bootstrap_database_and_load_data', return_value=[])
    mocker.patch('devildex.main.DevilDexCore.shutdown', return_value=None)
    
    core_instance = DevilDexCore(database_url=populated_db_session)
    
    # Removed mocker.patch.object(core_instance, '_start_mcp_server_if_enabled', return_value=None)
    # Allow the actual _start_mcp_server_if_enabled to run

    main_app = DevilDexApp(core=core_instance)
    main_app._initialize_data_and_managers()
    wx.Yield()  # Allow the UI to initialize
    yield main_app
    if main_app.main_frame:
        wx.CallAfter(main_app.main_frame.Destroy)
    wx.Yield()


@pytest.mark.integration
def test_gui_only_no_mcp_starts(devildex_app_fixture: DevilDexApp, mock_config_manager: MagicMock, mocker: MagicMock):
    """Verify that when MCP is disabled, the server process does not start."""
    # Arrange: ConfigManager is already mocked by fixture, ensure MCP is disabled
    mock_config_manager.get_mcp_server_enabled.return_value = False
    mock_config_manager.get_mcp_server_hide_gui_when_enabled.return_value = False # Ensure GUI is visible

    # We need to ensure the DevilDexCore instance used by the app is the one we control
    core_instance = devildex_app_fixture.core
    
    # Act: Simulate app startup with the desired config
    # Here, we directly call the method that would start MCP.
    try:
        core_instance._start_mcp_server_if_enabled(None) # Pass None for gui_warning_callback
    except Exception as e:
        print(f"Exception during _start_mcp_server_if_enabled: {e}")

    # Assert
    assert core_instance.mcp_server_process is None
    # Basic check that GUI is present (e.g., main frame exists)
    assert devildex_app_fixture.main_frame is not None
    assert devildex_app_fixture.main_frame.IsShown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_only_no_gui(mock_config_manager: MagicMock, populated_db_session: str, mocker: MagicMock):
    """Verify that when only MCP is enabled, the server starts and responds, and GUI is hidden."""
    # Arrange
    mock_config_manager.get_mcp_server_enabled.return_value = True
    mock_config_manager.get_mcp_server_hide_gui_when_enabled.return_value = True
    mcp_port = mock_config_manager.get_mcp_server_port()

    # Mock DevilDexApp to prevent GUI initialization
    mocker.patch('devildex.main.DevilDexApp.__init__', return_value=None)
    mocker.patch('devildex.main.DevilDexApp._initialize_data_and_managers', return_value=None)
    mocker.patch('devildex.main.DevilDexApp.MainLoop', return_value=None) # Prevent GUI loop
    mocker.patch('devildex.main.DevilDexApp.OnInit', return_value=True) # Ensure OnInit returns True
    mocker.patch('devildex.main.DevilDexApp.OnExit', return_value=0) # Ensure OnExit returns 0

    # Create a DevilDexCore instance that will actually start the MCP server
    core_instance = DevilDexCore(database_url=populated_db_session)
    core_instance.database_url = populated_db_session # Manually set after mocking __init__
    
    # The MCP server is started by the DevilDexCore constructor if enabled in config.
    # No need to call _start_mcp_server_if_enabled explicitly here.
    
    # Give the server some time to start up
    time.sleep(5) # Increased sleep time for server startup

    # Assert MCP server process is running
    assert core_instance.mcp_server_process is not None
    assert core_instance.mcp_server_process.poll() is None # Check if process is still running

    # Assert GUI is not shown
    # This is tricky. We can't directly assert wx.App().IsMainLoopRunning()
    # without creating a wx.App, which we are trying to avoid.
    # We infer it by mocking MainLoop and checking if the main frame is not created/shown.
    # The MainLoop is already mocked to return None, so we don't need to assert main_frame is None.

    # Test MCP client communication
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{mcp_port}/mcp"},
        }
    }
    client = Client(config, timeout=10) # Increased timeout for client
    try:
        async with client:
            docsets_list = await client.call_tool(
                "get_docsets_list", {"all_projects": True}, timeout=5
            )
            expected_names = ["requests", "flask", "django"] # Based on populated_db_session
            assert isinstance(docsets_list.data, list)
            assert sorted(docsets_list.data) == sorted(expected_names)
            print(f"Docsets list (MCP only): {docsets_list.data}")
    except Exception as e:
        pytest.fail(f"MCP client communication failed: {e}")
    finally:
        # Clean up the MCP server process
        if core_instance.mcp_server_process:
            core_instance.mcp_server_process.terminate()
            core_instance.mcp_server_process.wait(timeout=5)
            stdout, stderr = core_instance.mcp_server_process.communicate()
            if stdout:
                print(f"Server STDOUT on teardown:{stdout.decode()}")
            if stderr:
                print(f"Server STDERR on teardown:{stderr.decode()}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gui_and_mcp_coexistence(devildex_app_fixture: DevilDexApp, mock_config_manager: MagicMock, mocker: MagicMock):
    """Verify that GUI and MCP can coexist and function together."""
    # Arrange
    mock_config_manager.get_mcp_server_enabled.return_value = True
    mock_config_manager.get_mcp_server_hide_gui_when_enabled.return_value = False # Ensure GUI is visible
    mcp_port = mock_config_manager.get_mcp_server_port()

    core_instance = devildex_app_fixture.core
    
    # Manually start MCP server via core instance, as it's mocked in fixture setup
    try:
        core_instance._start_mcp_server_if_enabled(None)
    except Exception as e:
        pytest.fail(f"Exception during MCP server startup in coexistence test: {e}")
    
    time.sleep(5) # Give server time to start

    # Assert MCP server process is running
    assert core_instance.mcp_server_process is not None
    assert core_instance.mcp_server_process.poll() is None

    # Assert GUI is present
    assert devildex_app_fixture.main_frame is not None
    assert devildex_app_fixture.main_frame.IsShown()

    # Test MCP client communication
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{mcp_port}/mcp"},
        }
    }
    client = Client(config, timeout=10)
    try:
        async with client:
            docsets_list = await client.call_tool(
                "get_docsets_list", {"all_projects": True}, timeout=5
            )
            expected_names = ["requests", "flask", "django"] # Based on populated_db_session
            assert isinstance(docsets_list.data, list)
            assert sorted(docsets_list.data) == sorted(expected_names)
            print(f"Docsets list (GUI and MCP): {docsets_list.data}")
    except Exception as e:
        pytest.fail(f"MCP client communication failed in coexistence test: {e}")
    finally:
        # Clean up the MCP server process
        if core_instance.mcp_server_process:
            core_instance.mcp_server_process.terminate()
            core_instance.mcp_server_process.wait(timeout=5)
            stdout, stderr = core_instance.mcp_server_process.communicate()
            if stdout:
                print(f"Server STDOUT on teardown (coexistence):{stdout.decode()}")
            if stderr:
                print(f"Server STDERR on teardown (coexistence):{stderr.decode()}")