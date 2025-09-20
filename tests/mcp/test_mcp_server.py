"""module that tests mcp server."""

import logging
import os
import re
import socket
import subprocess
import tempfile
import time
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from devildex.core import DevilDexCore
from devildex.database import (
    Base,
    Docset,
    PackageInfo,
    RegisteredProject,
)
from devildex.local_data_parse import registered_project_parser
from devildex.local_data_parse.registered_project_parser import RegisteredProjectData

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def free_port() -> int:
    """Fixture to provide a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]



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


@pytest.fixture(scope="function")
def mcp_server_process(
    free_port: int, populated_db_session: tuple[str, Any, str, Path, DevilDexCore]
) -> Generator[tuple[int, str], Any, None]:
    """Fixture to start the MCP server as a subprocess."""
    db_url, SessionLocal, project_name, temp_docset_path, core_instance = populated_db_session

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
            server_process = subprocess.Popen(
                server_command,
                env=env,
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(10)  # Give server time to start
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
    mcp_server_process: tuple[int, str]
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
async def test_get_docsets_list_by_project(
    mcp_server_process: tuple[int, str]
) -> None:
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
    mcp_server_process: tuple[int, str]
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
async def test_get_page_content_success(
    mcp_server_process: tuple[int, str]
) -> None:
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
    mcp_server_process: tuple[int, str]
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
    mcp_server_process: tuple[int, str]
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
    mcp_server_process: tuple[int, str]
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
    mcp_server_process: tuple[int, str]
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
