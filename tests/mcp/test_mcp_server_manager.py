"""Test the McpServerManager class."""

from collections.abc import Generator
from typing import Any
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


@patch("subprocess.Popen")
@patch("time.sleep")
@patch("threading.Thread")
def test_start_server_success(
    mock_thread: MagicMock,
    mock_sleep: MagicMock,
    mock_popen: MagicMock,
    mcp_manager: McpServerManager,
) -> None:
    """Test start server success."""
    mock_process_instance = MagicMock()
    mock_process_instance.poll.return_value = None
    mock_popen.return_value = mock_process_instance

    def mock_thread_start() -> None:
        mcp_manager._run_server("sqlite:///:memory:")

    mock_thread_instance = MagicMock()
    mock_thread_instance.start.side_effect = mock_thread_start
    mock_thread.return_value = mock_thread_instance

    result = mcp_manager.start_server("sqlite:///:memory:")

    assert result is True
    mock_thread.assert_called_once()
    mock_thread_instance.start.assert_called_once()
    assert mcp_manager.server_process is mock_process_instance
    assert mcp_manager.server_thread is mock_thread_instance
    assert mcp_manager.is_server_running() is True


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
