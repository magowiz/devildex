import asyncio
from fastmcp import Client
from devildex.config_manager import ConfigManager # Import ConfigManager

async def main():
    config_manager = ConfigManager() # Instantiate ConfigManager
    mcp_port = config_manager.get_mcp_server_port() # Get port from config

    config = {
        "mcpServers": {
            "my_server": {"url": f"http://127.0.0.1:{mcp_port}/mcp"},
        }
    }
    client = Client(config, timeout=10)
    async with client:
        try:
            print("Calling 'get_docsets_list' tool...")
            response = await client.call_tool("get_docsets_list", {"all_projects": True})
            print("Response received:")
            print(response.data)
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
