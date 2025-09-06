"""mcp server module."""

from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")


class DevilDexMcp:
    """DevilDex MCP server."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DevilDexMcp, cls).__new__(cls)
        return cls._instance

    def __init__(self, enabled: bool = False) -> None:
        """Implement MCP server."""
        # Only initialize if it's the first time
        if not hasattr(self, '_initialized'):
            self.enabled = enabled
            self._initialized = True # Mark as initialized

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
        if not project and not all_projects:
            return {"error": "invalid parameters: project or all must be provided"}
        if project:
            return self._fetch_project_docsets(project_name=project)
        if all_projects:
            return self._fetch_all_projects_docset()
        return []

    def run(self) -> None:
        """Start server if enabled."""
        if self.enabled:
            mcp.run(transport="http", host="0.0.0.0", port=8001, path="/mcp")


# Global instance of DevilDexMcp
dd_mcp_instance = DevilDexMcp(enabled=True)

@mcp.tool
def get_docsets_list(
    project: str | None = None, all_projects: bool = False
) -> dict[str, str] | list[str]:
    """Get a list of docsets."""
    # Get the singleton instance
    instance = DevilDexMcp()
    return instance._get_docsets_list_internal(project=project, all_projects=all_projects)


if __name__ == "__main__":
    # Get the singleton instance and run it
    dd_mcp_instance = DevilDexMcp(enabled=True) # Pass enabled=True only on first creation
    dd_mcp_instance.run()
