"""mcp server module."""

# IMPORTANT: This MCP server is currently under active development and is INCOMPLETE.
# Only the 'get_docsets_list' tool is fully functional.
# Other functionalities are either placeholders or not yet implemented.
# Use with caution and refer to the documentation for current capabilities.

from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")


class DevilDexMcp:
    """DevilDex MCP server.

    This is a singleton class managing the Multi-Tool Command Protocol (MCP) server
    for DevilDex. It exposes various tools for external clients.
    WARNING: This server is currently INCOMPLETE. Only the 'get_docsets_list'
    tool is fully implemented and functional. Other tools or planned features
    are either placeholders or not yet developed.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DevilDexMcp, cls).__new__(cls)
        return cls._instance

    def __init__(self, enabled: bool = False, core_instance: Any = None, port: int = 8001) -> None:
        """Implement MCP server."""
        # Only initialize if it's the first time
        if not hasattr(self, "_initialized"):
            self.enabled = enabled
            self.core = core_instance  # Store the DevilDexCore instance
            self.port = port # Store the port
            self._initialized = True  # Mark as initialized

    def _fetch_all_projects_docset(self) -> list[str]:
        """Fetch all projects docset."""
        return ["requests", "flask", "django", "numpy", "pandas"]

    def _fetch_project_docsets(self, project_name: str) -> list[str]:
        """Fetch project docsets."""
        return ["requests", "flask"]

    def _get_docsets_list_internal(
        self, project: str | None = None, all_projects: bool = False
    ) -> dict[str, str] | list[str]:
        """Get a list of docsets."""
        if not self.core:
            return {"error": "DevilDexCore not initialized in MCP server."}

        if not project and not all_projects:
            return {
                "error": "invalid parameters: project or all_projects must be provided"
            }

        if project:
            docsets = self.core.get_docsets_info_for_project(project_name=project)
            return [d["name"] for d in docsets]

        if all_projects:
            docsets = self.core.get_all_docsets_info()
            return [d["name"] for d in docsets]

        return []

    def run(self) -> None:
        """Start server if enabled."""
        if self.enabled:
            mcp.run(transport="http", host="0.0.0.0", port=self.port, path="/mcp")





@mcp.tool
def get_docsets_list(
    project: str | None = None, all_projects: bool = False
) -> dict[str, str] | list[str]:
    """Get a list of docsets."""
    # Get the singleton instance
    instance = DevilDexMcp()
    return instance._get_docsets_list_internal(
        project=project, all_projects=all_projects
    )


if __name__ == "__main__":
    import logging
    import uvicorn
    server_logger = logging.getLogger(__name__)
    server_logger.info("MCP server standalone mode started.")

    from devildex.core import DevilDexCore
    import os
    from devildex.database import db_manager as database

    from devildex.config_manager import ConfigManager
    config = ConfigManager()
    mcp_port = config.get_mcp_server_port()

    db_url = os.getenv("DEVILDEX_MCP_DB_URL", None)
    server_logger.info(f"Using database URL: {db_url}")
    standalone_core = DevilDexCore(database_url=db_url)
    database.init_db(database_url=db_url)
    server_logger.info("Database initialized for standalone server.")
    dd_mcp_instance = DevilDexMcp(enabled=True, core_instance=standalone_core, port=mcp_port)
    server_logger.info(f"DevilDexMcp instance created. Port: {mcp_port}")

    try:
        server_logger.info(f"Starting Uvicorn server on port {mcp_port}...")
        mcp.run(transport="http", host="0.0.0.0", port=mcp_port, path="/mcp")
    except KeyboardInterrupt:
        server_logger.info("KeyboardInterrupt received. Shutting down.")
    except Exception as e:
        server_logger.error(f"Error running MCP server: {e}")
    server_logger.info("MCP server standalone mode finished.")
