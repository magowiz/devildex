import os  # Import os
import subprocess  # Import subprocess
import tempfile  # Import tempfile
import time  # Import time
from pathlib import Path  # Import Path

import pytest
from fastmcp import Client

from devildex import database
from devildex.core import DevilDexCore
from devildex.database import (  # Import necessary models
    Docset,
    PackageInfo,
    RegisteredProject,
)


@pytest.fixture(scope="module")
def mcp_server_with_populated_db():
    """Fixture to set up an in-memory SQLite database, populate it,
    and yield a DevilDexCore instance initialized with it.
    """
    # Use a temporary file for the SQLite database
    temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_file.close()  # Close the file handle, but keep the file
    db_url = f"sqlite:///{temp_db_file.name}"

    database.init_db(db_url)
    core_instance = DevilDexCore(database_url=db_url)

    # Populate the database with known data
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
        # Associate docset with project
        project1.docsets.append(docset_requests)
        session.commit()

        # Add PackageInfo and Docset for "flask"
        pkg_info_flask = PackageInfo(package_name="flask", summary="Web framework.")
        docset_flask = Docset(
            package_name="flask",
            package_version="2.0.0",
            status="available",
            package_info=pkg_info_flask,
        )
        session.add_all([pkg_info_flask, docset_flask])
        session.commit()
        # Associate docset with project
        project1.docsets.append(docset_flask)
        session.commit()

        # Add PackageInfo and Docset for "django" (not associated with any project for now)
        pkg_info_django = PackageInfo(package_name="django", summary="Web framework.")
        docset_django = Docset(
            package_name="django",
            package_version="3.2.0",
            status="available",
            package_info=pkg_info_django,
        )
        session.add_all([pkg_info_django, docset_django])
        session.commit()

        # Add PackageInfo and Docset for "numpy"
        pkg_info_numpy = PackageInfo(
            package_name="numpy", summary="Numerical computing."
        )
        docset_numpy = Docset(
            package_name="numpy",
            package_version="1.20.0",
            status="available",
            package_info=pkg_info_numpy,
        )
        session.add_all([pkg_info_numpy, docset_numpy])
        session.commit()

        # Add PackageInfo and Docset for "pandas"
        pkg_info_pandas = PackageInfo(package_name="pandas", summary="Data analysis.")
        docset_pandas = Docset(
            package_name="pandas",
            package_version="1.3.0",
            status="available",
            package_info=pkg_info_pandas,
        )
        session.add_all([pkg_info_pandas, docset_pandas])
        session.commit()

    # Start the MCP server as a subprocess
    server_process = None
    try:
        # Set the environment variable for the subprocess
        env = os.environ.copy()
        env["DEVILDEX_MCP_DB_URL"] = db_url

        # Command to run the server
        server_command = [
            "poetry",
            "run",
            "python",
            "src/devildex/mcp_server/server.py",
        ]

        # Start the server process
        server_process = subprocess.Popen(
            server_command,
            env=env,
            cwd=os.getcwd(),  # Run from project root
            stdout=subprocess.PIPE,  # Capture stdout
            stderr=subprocess.PIPE,  # Capture stderr
        )
        # Give the server some time to start up
        time.sleep(10)

        # Yield the core instance for tests to use
        yield core_instance

    finally:
        # Teardown: Terminate the server process and close the database
        if server_process:
            server_process.terminate()
            server_process.wait(timeout=5)  # Wait for process to terminate
            # Log any remaining output from the server process
            stdout, stderr = server_process.communicate()
            if stdout:
                print(f"\nServer STDOUT:\n{stdout.decode()}")
            if stderr:
                print(f"\nServer STDERR:\n{stderr.decode()}")
        database.DatabaseManager.close_db()
        # Clean up the temporary database file
        Path(temp_db_file.name).unlink(missing_ok=True)  # Delete the temporary file


@pytest.mark.asyncio
async def test_get_docsets_list_all_projects(
    mcp_server_with_populated_db: DevilDexCore,
) -> None:
    """Tests the 'get_docsets_list' tool with all_projects=True."""
    # The server under test (src/devildex/mcp_server/server.py) will use the
    # DevilDexCore instance provided by this fixture.
    # We need to ensure the server is running and configured to use this DB.
    # For this test, we assume the server is running and its DevilDexMcp
    # singleton has been initialized with the core_instance from this fixture.

    # This test still needs to connect to the *running* server.
    # The fixture populates the DB for the core instance that the server *should* use.
    # The actual connection is still via HTTP.

    config = {
        "mcpServers": {
            "my_server": {"url": "http://127.0.0.1:8001/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            docsets_list = await client.call_tool(
                "get_docsets_list", {"all_projects": True}, timeout=5
            )
            # Assert it's a list
            assert isinstance(docsets_list.data, list)
            # Assert it contains the expected items from the populated DB
            expected_names = ["requests", "flask", "django", "numpy", "pandas"]
            assert sorted(docsets_list.data) == sorted(
                expected_names
            )  # Check exact content
            print(f"Docsets list (all_projects): {docsets_list.data}")
        except Exception as e:
            pytest.fail(
                f"An error occurred during 'get_docsets_list' (all_projects) tool communication: {e}"
            )


@pytest.mark.asyncio
async def test_get_docsets_list_by_project(
    mcp_server_with_populated_db: DevilDexCore,
) -> None:
    """Tests the 'get_docsets_list' tool with a specific project."""
    config = {
        "mcpServers": {
            "my_server": {"url": "http://127.0.0.1:8001/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            # Use the project name from the populated DB
            docsets_list = await client.call_tool(
                "get_docsets_list", {"project": "TestProject"}, timeout=5
            )
            expected_names = ["requests", "flask"]
            assert isinstance(docsets_list.data, list)
            assert sorted(docsets_list.data) == sorted(
                expected_names
            )  # Check exact content
            print(f"Docsets list (by project): {docsets_list.data}")
        except Exception as e:
            pytest.fail(
                f"An error occurred during 'get_docsets_list' (by project) tool communication: {e}"
            )


@pytest.mark.asyncio
async def test_get_docsets_list_invalid_params(
    mcp_server_with_populated_db: DevilDexCore,
) -> None:
    """Tests the 'get_docsets_list' tool with invalid parameters (neither project nor all_projects)."""
    config = {
        "mcpServers": {
            "my_server": {"url": "http://127.0.0.1:8001/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            response = await client.call_tool("get_docsets_list", {}, timeout=5)
            expected_error = {
                "error": "invalid parameters: project or all_projects must be provided"
            }
            assert isinstance(response.data, dict)
            assert response.data == expected_error
            print(f"Docsets list (invalid params): {response.data}")
        except Exception as e:
            pytest.fail(
                f"An error occurred during 'get_docsets_list' (invalid params) tool communication: {e}"
            )