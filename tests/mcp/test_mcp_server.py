"""module that tests mcp server."""

import logging
import os
import re
import socket
import subprocess
import tempfile
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from devildex.core import DevilDexCore
from devildex.local_data_parse import registered_project_parser
from devildex.local_data_parse.registered_project_parser import RegisteredProjectData

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def free_port() -> int:
    """Fixture to provide a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mcp_server_process(
    free_port: int, populated_db_session: tuple[str, Any, str, Path, DevilDexCore]
) -> Generator[tuple[int, str], Any, None]:
    """Fixture to start the MCP server as a subprocess."""
    db_url, _, project_name, temp_docset_path, _ = populated_db_session

    project_data_to_save: RegisteredProjectData = {
        "project_name": project_name,
        "project_path": str(temp_docset_path),
        "python_executable": "/path/to/python",
    }
    registered_project_parser.save_active_registered_project(project_data_to_save)

    server_process = None
    with tempfile.TemporaryDirectory() as temp_user_data_dir:
        try:
            env = os.environ.copy()
            env["DEVILDEX_MCP_DB_URL"] = db_url
            env["DEVILDEX_MCP_SERVER_PORT"] = str(free_port)
            env["DEVILDEX_DEV_MODE"] = "1"  # Ensure dev mode is enabled
            env["DEVILDEX_DOCSET_BASE_OUTPUT_PATH"] = str(temp_docset_path)
            env["DEVILDEX_USER_DATA_DIR"] = str(temp_user_data_dir)
            server_command = [
                "poetry",
                "run",
                "python",
                "src/devildex/mcp_server/server.py",
            ]
            server_process = subprocess.Popen(  # noqa: S603
                server_command,
                env=env,
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(10)
            yield free_port, project_name
        finally:
            if server_process:
                server_process.terminate()
                server_process.wait(timeout=5)
                stdout, stderr = server_process.communicate()
                if stdout:
                    logger.info(f"\nServer STDOUT:\n{stdout.decode()}")
                if stderr:
                    logger.error(f"\nServer STDERR:\n{stderr.decode()}")


@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_get_docsets_list_all_projects(
    mcp_server_process: tuple[int, str],
) -> None:
    """Tests the 'get_docsets_list' tool with all_projects=True."""
    free_port, _ = mcp_server_process
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            docsets_list = await client.call_tool(
                "get_docsets_list", {"all_projects": True}, timeout=5
            )
            assert isinstance(docsets_list.data, list)
            expected_names = ["requests", "flask", "django", "numpy", "pandas"]
            assert sorted(docsets_list.data) == sorted(expected_names)
            logger.info(f"Docsets list (all_projects): {docsets_list.data}")
        except Exception as e:
            pytest.fail(
                "An error occurred during 'get_docsets_list' "
                f"(all_projects) tool communication: {e}"
            )


@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_get_docsets_list_by_project(mcp_server_process: tuple[int, str]) -> None:
    """Tests the 'get_docsets_list' tool with a specific project."""
    free_port, project_name = mcp_server_process
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            docsets_list = await client.call_tool(
                "get_docsets_list", {"project": project_name}, timeout=5
            )
            expected_names = ["requests", "flask"]
            assert isinstance(docsets_list.data, list)
            assert sorted(docsets_list.data) == sorted(expected_names)
            logger.info(f"Docsets list (by project): {docsets_list.data}")
        except Exception as e:
            pytest.fail(
                "An error occurred during 'get_docsets_list' "
                f"(by project) tool communication: {e}"
            )


@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_get_docsets_list_invalid_params(
    mcp_server_process: tuple[int, str],
) -> None:
    """Tests the 'get_docsets_list' tool with invalid parameters."""
    free_port, _ = mcp_server_process
    config = {
        "mcpServers": {"my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"}},
    }
    client = Client(config, timeout=10)
    async with client:
        try:
            response = await client.call_tool("get_docsets_list", {}, timeout=5)
            expected_error = {
                "error": "invalid parameters: project or all_projects must be provided"
            }
            assert isinstance(response.data, dict)
            assert response.data == expected_error
            logger.info(f"Docsets list (invalid params): {response.data}")
        except Exception as e:
            pytest.fail(
                "An error occurred during 'get_docsets_list' (invalid params)"
                f" tool communication: {e}"
            )


@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_get_page_content_success(mcp_server_process: tuple[int, str]) -> None:
    """Tests the 'get_page_content' tool for successful retrieval."""
    free_port, _ = mcp_server_process
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            response = await client.call_tool(
                "get_page_content",
                {"package": "requests", "version": "2.25.1", "page": "page1.html"},
                timeout=5,
            )
            assert response.data == "Requests Page 1\n---------------"
        except Exception as e:
            pytest.fail(
                f"An error occurred during 'get_page_content' tool communication: {e}"
            )


@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_get_page_content_default_page(
    mcp_server_process: tuple[int, str],
) -> None:
    """Tests the 'get_page_content' tool for default page retrieval."""
    free_port, _ = mcp_server_process
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.00.1:{free_port}/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            response = await client.call_tool(
                "get_page_content",
                {"package": "requests", "version": "2.25.1"},
                timeout=5,
            )
            assert response.data == "Requests Index\n=============="
        except Exception as e:
            pytest.fail(
                f"An error occurred during 'get_page_content' tool communication: {e}"
            )


@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_get_page_content_non_existent_page(
    mcp_server_process: tuple[int, str],
) -> None:
    """Tests the 'get_page_content' tool for a non-existent page."""
    free_port, _ = mcp_server_process
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            response = await client.call_tool(
                "get_page_content",
                {
                    "package": "requests",
                    "version": "2.25.1",
                    "page": "non_existent.html",
                },
                timeout=5,
            )
            assert "error" in response.data
            assert re.search(
                r"Page '.*?' not found in docset '.*?' version '.*?'.",
                response.data["error"],
            )
        except Exception as e:
            pytest.fail(
                f"An error occurred during 'get_page_content' tool communication: {e}"
            )


@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_get_page_content_non_existent_package_version(
    mcp_server_process: tuple[int, str],
) -> None:
    """Tests the 'get_page_content' tool for a non-existent package/version."""
    free_port, _ = mcp_server_process
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            response = await client.call_tool(
                "get_page_content",
                {"package": "non_existent", "version": "1.0.0", "page": "index.html"},
                timeout=5,
            )
            assert "error" in response.data
            assert re.search(
                r"Docset for package '.*?' version '.*?' not found",
                response.data["error"],
            )
        except Exception as e:
            pytest.fail(
                f"An error occurred during 'get_page_content' tool communication: {e}"
            )


@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_get_page_content_path_traversal_attempt(
    mcp_server_process: tuple[int, str],
) -> None:
    """Tests the 'get_page_content' tool for path traversal attempts."""
    free_port, _ = mcp_server_process
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            response = await client.call_tool(
                "get_page_content",
                {
                    "package": "requests",
                    "version": "2.25.1",
                    "page": "../../../secret.txt",
                },
                timeout=5,
            )
            assert "error" in response.data
            assert "Invalid page path" in response.data["error"]
        except Exception as e:
            pytest.fail(
                f"An error occurred during 'get_page_content' tool communication: {e}"
            )
