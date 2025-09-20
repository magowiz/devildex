"""A simple client to test the MCP server functionality."""
import asyncio
import logging

from fastmcp import Client

from devildex.config_manager import ConfigManager  # Import ConfigManager

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the MCP client test."""
    config_manager = ConfigManager()  # Instantiate ConfigManager
    mcp_port = config_manager.get_mcp_server_port()  # Get port from config

    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{mcp_port}/mcp"},
        }
    }
    client = Client(config, timeout=10)
    async with client:
        try:
            logger.info("Calling 'get_docsets_list' tool...")
            response = await client.call_tool(
                "get_docsets_list", {"all_projects": True}
            )
            logger.info("Response received:")
            logger.info(response.data)
        except Exception:
            logger.exception("An error occurred")


if __name__ == "__main__":
    asyncio.run(main())
