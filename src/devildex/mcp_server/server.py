"""mcp server module."""

# IMPORTANT: This MCP server is currently under active development and is INCOMPLETE.
# Only the 'get_docsets_list' tool is fully functional.
# Other functionalities are either placeholders or not yet implemented.
# Use with caution and refer to the documentation for current capabilities.

import logging
import os
import pathlib
from typing import Any

from fastmcp import FastMCP
from markdownify import markdownify

from devildex.core import DevilDexCore  # Import DevilDexCore
from devildex.database import db_manager as database

# IMPORTANT: This MCP server is currently under active development and is INCOMPLETE.
# Only the 'get_docsets_list' tool is fully functional.
# Other functionalities are either placeholders or not yet implemented.
# Use with caution and refer to the documentation for current capabilities.

mcp = FastMCP("Demo 🚀")

_core_instance: DevilDexCore | None = None


def set_core_instance(core_instance: DevilDexCore) -> None:
    """Set the global core instance."""
    global _core_instance  # noqa: PLW0603
    _core_instance = core_instance


@mcp.tool
async def get_docsets_list(
    project: str | None = None, all_projects: bool = False
) -> dict[str, str] | list[str]:
    """Get a list of docsets."""
    if not _core_instance:
        return {"error": "DevilDexCore not initialized in MCP server."}

    if not project and not all_projects:
        return {"error": "invalid parameters: project or all_projects must be provided"}

    if project:
        docsets = _core_instance.get_docsets_info_for_project(project_name=project)
        server_logger.info(f"MCP Server: Docsets for project '{project}': {docsets}")
        return [d["name"] for d in docsets]

    if all_projects:
        docsets = _core_instance.get_all_docsets_info()
        server_logger.info(f"MCP Server: All docsets: {docsets}")  # Added logging
        return [d["name"] for d in docsets]

    return []


def _html_to_markdown(html_content: str) -> str:
    return markdownify(html_content)


def _is_valid_path(base_path: str, requested_path: str) -> bool:
    """Check if the requested_path is strictly within the base_path."""
    try:
        base_path_obj = pathlib.Path(base_path).resolve()
        requested_path_obj = pathlib.Path(requested_path).resolve()
        return requested_path_obj.is_relative_to(base_path_obj)
    except OSError:
        return False


def _get_docset_root_path(
    package: str, version: str | None
) -> tuple[pathlib.Path | None, str | None]:
    """Get docset root path and handle initialization/not found errors."""
    if not _core_instance:
        return None, "DevilDexCore not initialized in MCP server."

    docset_path_obj = _core_instance.get_docset_path(
        package_name=package, version=version
    )
    server_logger.info(
        f"MCP Server: Attempting to access docset path: {docset_path_obj}"
    )
    if docset_path_obj is None:
        return None, f"Docset for package '{package}' version '{version}' not found."
    server_logger.info(
        f"MCP Server: Does docset path exist? {docset_path_obj.exists()}"
    )
    if not docset_path_obj.exists():
        return None, f"Docset for package '{package}' version '{version}' not found."

    return docset_path_obj, None


def _validate_page_path(
    docset_root_path_obj: pathlib.Path, page: str, package: str, version: str | None
) -> tuple[pathlib.Path | None, str | None]:
    """Validate the requested page path against path traversal and existence."""
    full_requested_page_path = docset_root_path_obj / page

    if not _is_valid_path(str(docset_root_path_obj), str(full_requested_page_path)):
        return None, f"Invalid page path: path traversal attempt detected for '{page}'."

    server_logger.info(
        f"MCP Server: Attempting to access page path: {full_requested_page_path}"
    )
    server_logger.info(
        f"MCP Server: Is page file? {full_requested_page_path.is_file()}"
    )
    if not full_requested_page_path.is_file():
        return None, (
            f"Page '{page}' not found in docset '{package}' version '{version}'."
        )
    return full_requested_page_path, None


def _read_and_convert_content(
    file_path_obj: pathlib.Path, page: str
) -> tuple[str | None, str | None]:
    """Read file content and convert to Markdown if applicable."""
    try:
        with open(file_path_obj, encoding="utf-8") as content_file:
            content = content_file.read()
            if page.lower().endswith((".html", ".htm")):
                return _html_to_markdown(content), None
            else:
                return content, None
    except UnicodeDecodeError:
        return None, (
            f"Failed to decode content of page '{page}'. "
            "It might not be a text file."
        )
    except OSError as e:
        return None, f"File system error reading page '{page}': {e!s}"
    except RuntimeError as e:
        logging.error(
            f"An unexpected runtime error occurred while processing page '{page}': {e}",
            exc_info=True,
        )
        return None, (
            f"An unexpected runtime error occurred while processing page '{page}'."
        )


@mcp.tool
async def get_page_content(
    package: str, page: str = "index.html", version: str | None = None
) -> str | dict[str, str]:
    """Get the content of a specific page within a docset.

    Args:
        package (str): The name of the package for which to retrieve
            docset content (e.g., "black").
        page (str, optional): The name of the page to retrieve within the
            docset (e.g., "index.html", "getting_started.html").
                              Defaults to "index.html".
        version (str | None, optional): The specific version of the package's
            docset to retrieve (e.g., "main", "24.4.2").
                                        If not provided, the system will attempt to
                                        automatically detect the version
                                        by scanning the package's docset directory
                                        and its immediate subdirectories
                                        for an 'index.html' file.

    Returns:
        str | dict[str, str]: The content of the requested page as a string,
            or a dictionary containing an "error" key with a descriptive
            error message if the page or docset could not be found or accessed.

    """
    docset_root_path_obj, error_message = _get_docset_root_path(package, version)
    if error_message:
        return {"error": error_message}

    full_requested_page_path_obj, error_message = _validate_page_path(
        docset_root_path_obj, page, package, version
    )
    if error_message:
        return {"error": error_message}

    content, error_message = _read_and_convert_content(
        full_requested_page_path_obj, page
    )
    if error_message:
        return {"error": error_message}

    return content


@mcp.tool
async def delete_docset(package: str, version: str | None = None) -> dict[str, str]:
    """Delete a docset."""
    n_found = len(_core_instance.search_for_docset(package, version))
    if n_found == 1:
        deleted = _core_instance.delete_docset(package, version)
        if deleted:
            return {"info": f"Docset '{package}' deleted successfully."}
        else:
            return {"error": f"Failed to delete docset '{package}'."}
    if n_found == 0:
        return {
            "error": f"No docset found for package '{package}' "
            f"and version '{version or 'NA'}'."
        }
    return {
        "error": f"Multiple docsets found for package '{package}' try to specify the version."
    }


@mcp.tool
async def get_task_status(task_id: str) -> dict[str, Any]:
    """Get the current status and result of an asynchronous docset generation task."""
    if not _core_instance:
        return {
            "status": "FAILED",
            "result": "DevilDexCore not initialized in MCP server.",
        }

    return _core_instance.get_task_status(task_id)


@mcp.tool
async def generate_docset(
    package: str, version: str, project_urls: dict | None = None, force: bool = False
) -> dict[str, str]:
    """Initiate asynchronous docset generation and return a task ID."""
    if not _core_instance:
        return {"error": "DevilDexCore not initialized in MCP server."}
    if not package or not version:
        return {"error": "invalid parameters: package and version must be provided"}

    package_data = {
        "name": package,
        "version": version,
        "project_urls": project_urls or {},
    }
    task_id = _core_instance.generate_docset(package_data=package_data, force=force)

    return {
        "task_id": task_id,
        "status": "PENDING",
        "message": "Docset generation initiated.",
    }


if __name__ == "__main__":

    server_logger = logging.getLogger(__name__)
    server_logger.info("MCP server standalone mode started.")
    server_logger.info(f"Current Working Directory (subprocess): {os.getcwd()}")

    from pathlib import Path

    from devildex.config_manager import ConfigManager
    from devildex.core import DevilDexCore
    from devildex.database import db_manager as database

    config = ConfigManager()
    mcp_port = os.getenv("DEVILDEX_MCP_SERVER_PORT")
    mcp_port = int(mcp_port) if mcp_port else config.get_mcp_server_port()

    db_url = os.getenv("DEVILDEX_MCP_DB_URL", None)
    server_logger.info(f"Using database URL: {db_url}")

    docset_base_output_path_env = os.getenv("DEVILDEX_DOCSET_BASE_OUTPUT_PATH", None)

    if docset_base_output_path_env:
        standalone_core = DevilDexCore(
            database_url=db_url,
            docset_base_output_path=Path(docset_base_output_path_env),
        )
    else:
        standalone_core = DevilDexCore(database_url=db_url)
    database.init_db(database_url=db_url)
    server_logger.info("Database initialized for standalone server.")

    set_core_instance(standalone_core)

    server_logger.info(f"Starting Uvicorn server on port {mcp_port}...")

    try:
        mcp.run(transport="http", host="127.0.0.1", port=mcp_port, path="/mcp")
    except KeyboardInterrupt:
        server_logger.info("KeyboardInterrupt received. Shutting down.")
    except RuntimeError:
        server_logger.exception("Error running MCP server: A runtime error occurred.")
    except OSError:
        server_logger.exception(
            "Error running MCP server: An OS-related error occurred."
        )
    except Exception:
        server_logger.exception("Error running MCP server")
    server_logger.info("MCP server finished.")
