"""mcp server module."""

from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")


class DevilDexMcp:
    """DevilDex MCP server."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DevilDexMcp, cls).__new__(cls)
        return cls._instance

    def __init__(self, enabled: bool = False, core_instance: Any = None) -> None:
        """Implement MCP server."""
        # Only initialize if it's the first time
        if not hasattr(self, "_initialized"):
            self.enabled = enabled
            self.core = core_instance  # Store the DevilDexCore instance
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
            mcp.run(transport="http", host="0.0.0.0", port=8001, path="/mcp")





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
    # Get the singleton instance and run it
    from devildex.core import DevilDexCore
    import os # Add import for os
    from devildex import database # Add import for database

    db_url = os.getenv("DEVILDEX_MCP_DB_URL", None) # Get DB URL from environment variable
    standalone_core = DevilDexCore(database_url=db_url) # Pass DB URL to DevilDexCore
    database.init_db(database_url=db_url) # Explicitly initialize the database for the server
    dd_mcp_instance = DevilDexMcp(enabled=True, core_instance=standalone_core)
    dd_mcp_instance.run()
