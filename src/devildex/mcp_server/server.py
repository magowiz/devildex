"""mcp server module."""

# IMPORTANT: This MCP server is currently under active development and is INCOMPLETE.
# Only the 'get_docsets_list' tool is fully functional.
# Other functionalities are either placeholders or not yet implemented.
# Use with caution and refer to the documentation for current capabilities.

import logging
import os
import sys  # Added for sys.path
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")

standalone_core: Any = None


@mcp.tool
def get_docsets_list(
    project: str | None = None, all_projects: bool = False
) -> dict[str, str] | list[str]:
    """Get a list of docsets."""
    if not standalone_core:
        return {"error": "DevilDexCore not initialized in MCP server."}

    if not project and not all_projects:
        return {"error": "invalid parameters: project or all_projects must be provided"}

    if project:
        docsets = standalone_core.get_docsets_info_for_project(project_name=project)
        return [d["name"] for d in docsets]

    if all_projects:
        docsets = standalone_core.get_all_docsets_info()
        return [d["name"] for d in docsets]

    return []


if __name__ == "__main__":

    server_logger = logging.getLogger(__name__)
    server_logger.info("MCP server standalone mode started.")

    from devildex.config_manager import ConfigManager
    from devildex.core import DevilDexCore
    from devildex.database import db_manager as database

    config = ConfigManager()
    mcp_port = os.getenv("DEVILDEX_MCP_SERVER_PORT")
    mcp_port = int(mcp_port) if mcp_port else config.get_mcp_server_port()

    db_url = os.getenv("DEVILDEX_MCP_DB_URL", None)
    server_logger.info(f"Using database URL: {db_url}")
    standalone_core = DevilDexCore(database_url=db_url)
    database.init_db(database_url=db_url)
    server_logger.info("Database initialized for standalone server.")

    server_logger.info(f"Starting Uvicorn server on port {mcp_port}...")

    # Debugging prints
    server_logger.info(f"Server sys.path: {sys.path}")
    server_logger.info(f"Server os.environ: {os.environ}")

    try:
        # Reverted to mcp.run() as per original intention, and to debug
        mcp.run(transport="http", host="127.0.0.1", port=mcp_port, path="/mcp")
    except KeyboardInterrupt:
        server_logger.info("KeyboardInterrupt received. Shutting down.")
    except Exception:
        server_logger.exception("Error running MCP server")
    server_logger.info("MCP server standalone mode finished.")
