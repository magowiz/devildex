import pytest
import pytest_asyncio
from fastmcp import Client # Keep Client

# We will assume the server is running on http://127.0.0.1:8001
# You need to start the server (src/devildex/mcp_server/server.py)
# in a separate terminal before running these tests.

@pytest.mark.asyncio
async def test_get_docsets_list_all_projects() -> None:
    """
    Tests the 'get_docsets_list' tool with all_projects=True.
    """
    config = {
        "mcpServers": {
            "my_server": {"url": "http://127.0.0.1:8001/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            # Call the tool without the 'my_server.' prefix
            docsets_list = await client.call_tool("get_docsets_list", {"all_projects": True}, timeout=5)
            expected_docsets = ["requests", "flask", "django", "numpy", "pandas"]
            assert isinstance(docsets_list.data, list)
            assert docsets_list.data == expected_docsets
            print(f"Docsets list (all_projects): {docsets_list.data}")
        except Exception as e:
            pytest.fail(f"An error occurred during 'get_docsets_list' (all_projects) tool communication: {e}")

@pytest.mark.asyncio
async def test_get_docsets_list_by_project() -> None:
    """
    Tests the 'get_docsets_list' tool with a specific project.
    """
    config = {
        "mcpServers": {
            "my_server": {"url": "http://127.0.0.1:8001/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            # Call the tool without the 'my_server.' prefix
            docsets_list = await client.call_tool("get_docsets_list", {"project": "some_project"}, timeout=5)
            expected_docsets = ["requests", "flask"]
            assert isinstance(docsets_list.data, list)
            assert docsets_list.data == expected_docsets
            print(f"Docsets list (by project): {docsets_list.data}")
        except Exception as e:
            pytest.fail(f"An error occurred during 'get_docsets_list' (by project) tool communication: {e}")

@pytest.mark.asyncio
async def test_get_docsets_list_invalid_params() -> None:
    """
    Tests the 'get_docsets_list' tool with invalid parameters (neither project nor all_projects).
    """
    config = {
        "mcpServers": {
            "my_server": {"url": "http://127.0.0.1:8001/mcp"},
        }
    }
    client = Client(config, timeout=5)
    async with client:
        try:
            # Call the tool without the 'my_server.' prefix
            response = await client.call_tool("get_docsets_list", {}, timeout=5)
            expected_error = {"error": "invalid parameters: project or all must be provided"}
            assert isinstance(response.data, dict)
            assert response.data == expected_error
            print(f"Docsets list (invalid params): {response.data}")
        except Exception as e:
            pytest.fail(f"An error occurred during 'get_docsets_list' (invalid params) tool communication: {e}")