"""Module that tests mcp server."""

import asyncio
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
from devildex.database.models import PackageDetails
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
def create_mcp_docset_files(
    populated_db_session: tuple[
        str, Any, str, Path, DevilDexCore, list[PackageDetails]
    ],
) -> None:
    """Create the docset files needed for the MCP tests."""
    _, _, _, temp_docset_path, _, _ = populated_db_session
    docset_names_versions = {
        "requests": "2.25.1",
    }
    for name, version in docset_names_versions.items():
        docset_path = temp_docset_path / name / version
        docset_path.mkdir(parents=True, exist_ok=True)
        if name == "requests":
            (docset_path / "index.html").write_text("Requests Index\n=============")
            (docset_path / "page1.html").write_text("Requests Page 1\n---------------")


@pytest.fixture
def mcp_server_process(
    free_port: int,
    populated_db_session: tuple[str, Any, str, Path, DevilDexCore, list[Any]],
    create_mcp_docset_files: None,
) -> Generator[tuple[int, str], Any, None]:
    """Fixture to start the MCP server as a subprocess."""
    db_url, _, project_name, temp_docset_path, _, _ = populated_db_session

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
                "An error occurred during 'get_docsets_list' (all_projects) tool "
                f"communication: {e}"
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
                "An error occurred during 'get_docsets_list' (by project) tool "
                f"communication: {e}"
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
                "An error occurred during 'get_docsets_list' (invalid params) "
                f"tool communication: {e}"
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
                "An error occurred during 'get_page_content' tool communication: "
                f"{e}"
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
            "my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"},
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
            assert response.data == "Requests Index\n============="
        except Exception as e:
            pytest.fail(
                "An error occurred during 'get_page_content' tool communication: "
                f"{e}"
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
                "An error occurred during 'get_page_content' tool communication: "
                f"{e}"
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
                "An error occurred during 'get_page_content' tool communication: "
                f"{e}"
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
                "An error occurred during 'get_page_content' tool communication: "
                f"{e}"
            )

@pytest.mark.xdist_group(name="mcp_server_tests")
@pytest.mark.asyncio
async def test_generate_and_delete_docset(mcp_server_process: tuple[int, str]) -> None:
    """Tests the 'generate_docset', 'get_task_status', and 'delete_docset' tools."""
    free_port, _ = mcp_server_process
    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{free_port}/mcp"},
        }
    }
    client = Client(config, timeout=45)
    package_name = "six"
    package_version = "1.16.0"

    async with client:
        # 1. Generate Docset
        generation_response = await client.call_tool(
            "generate_docset",
            {
                "package": package_name,
                "version": package_version,
            },
            timeout=30,
        )
        assert "task_id" in generation_response.data
        task_id = generation_response.data["task_id"]

        # 2. Poll Task Status
        status_response = None
        for _ in range(20):  # Poll for 40 seconds max
            await asyncio.sleep(2)
            status_response = await client.call_tool(
                "get_task_status", {"task_id": task_id}, timeout=5
            )
            if status_response.data["status"] in ["COMPLETED", "FAILED"]:
                break

        assert status_response is not None
        assert status_response.data["status"] == "COMPLETED", f"Task failed with result: {status_response.data.get('result')}"
        assert status_response.data["result"][0] is True

        delete_response = await client.call_tool(
            "delete_docset",
            {"package": package_name, "version": package_version},
            timeout=10,
        )
        assert "info" in delete_response.data
        assert f"Docset '{package_name}' deleted successfully." in delete_response.data["info"]

        delete_again_response = await client.call_tool(
            "delete_docset",
            {"package": package_name, "version": package_version},
            timeout=10,
        )
        assert "error" in delete_again_response.data
        assert "No docset found" in delete_again_response.data["error"]
