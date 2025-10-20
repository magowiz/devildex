"""Test the McpServerManager class."""

import os
import tempfile
import subprocess
import requests
from pathlib import Path
from collections.abc import Generator
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devildex.mcp_server.mcp_server_manager import McpServerManager

MOCK_MCP_PORT = 12345


@pytest.fixture
def mock_config_manager() -> Generator[MagicMock | AsyncMock, Any, None]:
    """Create a mock ConfigManager instance for testing."""
    with patch("devildex.mcp_server.mcp_server_manager.ConfigManager") as mock_config:
        mock_instance = mock_config.return_value
        mock_instance.get_mcp_server_port.return_value = MOCK_MCP_PORT
        yield mock_config


@pytest.fixture
def mcp_manager(mock_config_manager: MagicMock) -> McpServerManager:
    """Create a McpServerManager instance for testing."""
    manager = McpServerManager()
    manager.server_process = None
    manager.server_thread = None
    return manager


def test_mcp_manager_initialization(mcp_manager: McpServerManager) -> None:
    """Test initialization of McpServerManager."""
    assert mcp_manager.mcp_port == MOCK_MCP_PORT
    assert mcp_manager.server_process is None
    assert mcp_manager.server_thread is None


def test_start_server_success(mcp_manager: McpServerManager) -> None:
    """Test start server success by actually starting the server and verifying its health."""
    temp_db_path: Optional[Path] = None
    original_pythonpath: Optional[str] = os.getenv("PYTHONPATH")
    original_db_url_env: Optional[str] = os.getenv("DEVILDEX_MCP_DB_URL")
    original_port_env: Optional[str] = os.getenv("DEVILDEX_MCP_SERVER_PORT")

    try:
        # 1. Setup a temporary database
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temp_db_file:
            temp_db_path = Path(temp_db_file.name)
        db_url = f"sqlite:///{temp_db_path.resolve()}"

        # 2. Set environment variables for alembic and server
        project_root = Path(__file__).parent.parent.parent
        os.environ["PYTHONPATH"] = str(project_root / "src") + os.pathsep + (original_pythonpath or "")
        os.environ["DEVILDEX_MCP_DB_URL"] = db_url
        os.environ["DEVILDEX_MCP_SERVER_PORT"] = str(mcp_manager.mcp_port)

        # 3. Run Alembic migrations
        alembic_ini_path = project_root / "src" / "devildex" / "alembic.ini"
        alembic_script_location = project_root / "src" / "devildex" / "alembic"

        alembic_command = [
            "alembic",
            "-c", str(alembic_ini_path),
            "--raiseerr",
            "upgrade",
            "head"
        ]
        print(f"Running alembic command: {' '.join(alembic_command)}")
        alembic_process = subprocess.run(
            alembic_command,
            env=os.environ,
            capture_output=True,
            text=True,
            check=True # Raise an exception if the command fails
        )
        print(f"Alembic stdout:\n{alembic_process.stdout}")
        if alembic_process.stderr:
            print(f"Alembic stderr:\n{alembic_process.stderr}")

        # 4. Start the MCP server
        started = mcp_manager.start_server(db_url)
        assert started is True
        assert mcp_manager.is_server_running() is True

        # 5. Verify server is running by hitting the health endpoint
        response = requests.get(mcp_manager.health_url, timeout=5)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    finally:
        # 6. Stop the server
        mcp_manager.stop_server()
        assert mcp_manager.is_server_running() is False

        # 7. Cleanup environment variables
        if original_pythonpath is not None:
            os.environ["PYTHONPATH"] = original_pythonpath
        else:
            if "PYTHONPATH" in os.environ:
                del os.environ["PYTHONPATH"]

        if original_db_url_env is not None:
            os.environ["DEVILDEX_MCP_DB_URL"] = original_db_url_env
        else:
            if "DEVILDEX_MCP_DB_URL" in os.environ:
                del os.environ["DEVILDEX_MCP_DB_URL"]

        if original_port_env is not None:
            os.environ["DEVILDEX_MCP_SERVER_PORT"] = original_port_env
        else:
            if "DEVILDEX_MCP_SERVER_PORT" in os.environ:
                del os.environ["DEVILDEX_MCP_SERVER_PORT"]

        # 8. Cleanup temporary database file
        if temp_db_path and temp_db_path.exists():
            temp_db_path.unlink()


def test_is_server_running_true(mcp_manager: McpServerManager) -> None:
    """Test is server running true."""
    mcp_manager.server_process = MagicMock()
    mcp_manager.server_process.poll.return_value = None
    mcp_manager.server_thread = MagicMock()
    mcp_manager.server_thread.is_alive.return_value = True
    assert mcp_manager.is_server_running() is True


def test_is_server_running_false_no_thread(mcp_manager: McpServerManager) -> None:
    """Test is server running false no thread."""
    mcp_manager.server_process = None
    mcp_manager.server_thread = None
    assert mcp_manager.is_server_running() is False


def test_is_server_running_false_thread_dead(mcp_manager: McpServerManager) -> None:
    """Test is server running false thread dead."""
    mcp_manager.server_process = MagicMock()
    mcp_manager.server_process.poll.return_value = None
    mcp_manager.server_thread = MagicMock()
    mcp_manager.server_thread.is_alive.return_value = False
    assert mcp_manager.is_server_running() is False


def test_is_server_running_false_process_dead(mcp_manager: McpServerManager) -> None:
    """Test is server running false process dead."""
    mcp_manager.server_process = MagicMock()
    mcp_manager.server_process.poll.return_value = 1
    mcp_manager.server_thread = MagicMock()
    mcp_manager.server_thread.is_alive.return_value = True
    assert mcp_manager.is_server_running() is False
    assert mcp_manager.server_process is None
    assert mcp_manager.server_thread is None
