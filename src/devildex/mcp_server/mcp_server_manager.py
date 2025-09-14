"""MCP Server Manager module."""

import logging
import os
import subprocess
import threading
import time
from typing import Optional

import requests

from devildex.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class McpServerManager:
    """Manages the lifecycle of the MCP server."""

    def __init__(self) -> None:
        """Initialize the McpServerManager."""
        self.server_thread: Optional[threading.Thread] = None
        self.server_process: Optional[subprocess.Popen] = None
        self.mcp_port = ConfigManager().get_mcp_server_port()
        self.mcp_url = f"http://127.0.0.1:{self.mcp_port}/mcp"
        self.health_url = f"http://127.0.0.1:{self.mcp_port}/mcp/health"
        self.shutdown_url = f"http://127.0.0.1:{self.mcp_port}/shutdown"

    def _run_server(self, db_url: str) -> None:
        """Run the MCP server process."""
        env = os.environ.copy()
        env["DEVILDEX_MCP_DB_URL"] = db_url
        env["DEVILDEX_MCP_SERVER_PORT"] = str(self.mcp_port)
        if os.getenv("DEVILDEX_DEV_MODE") == "1":
            env["DEVILDEX_DEV_MODE"] = "1"

        server_command = [
            "poetry",
            "run",
            "python",
            "src/devildex/mcp_server/server.py",
        ]

        try:
            self.server_process = subprocess.Popen(
                server_command,
                env=env,
                stdout=subprocess.PIPE,  # Capture stdout
                stderr=subprocess.PIPE,  # Capture stderr
                text=True,  # Decode stdout/stderr as text
            )
            logger.info(
                f"MCP server process started with PID: {self.server_process.pid}"
            )
            # Continuously read stdout/stderr to prevent buffer full issues
            for line in self.server_process.stdout:
                logger.info(f"[MCP Server STDOUT]: {line.strip()}")
            for line in self.server_process.stderr:
                logger.error(f"[MCP Server STDERR]: {line.strip()}")

        except FileNotFoundError:
            logger.exception(
                f"Error: Could not find the server script at {server_command[1]}"
            )
        except Exception:
            logger.exception("Failed to start MCP server process")
        finally:
            if self.server_process and self.server_process.poll() is None:
                logger.warning("MCP server process did not exit cleanly. Terminating.")
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                if self.server_process.poll() is None:
                    self.server_process.kill()
            logger.info("MCP server thread finished.")

    def start_server(self, db_url: str) -> bool:
        """Start the MCP server in a separate thread and waits for it to be ready."""
        if self.is_server_running():
            logger.info("MCP server is already running.")
            return True

        logger.info("Attempting to start MCP server thread...")
        self.server_thread = threading.Thread(target=self._run_server, args=(db_url,))
        self.server_thread.daemon = (
            True  # Allow main program to exit even if thread is running
        )
        self.server_thread.start()

        # Wait for the server to be ready
        start_time = time.time()
        while time.time() - start_time < 30:  # 30-second timeout for server readiness
            try:
                response = requests.get(self.health_url, timeout=1)
                if response.status_code == 200:
                    logger.info("MCP server is ready.")
                    return True
            except requests.ConnectionError:
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Health check failed with unexpected error: {e}")
                time.sleep(0.5)

        logger.error("MCP server did not become ready within the timeout period.")
        self.stop_server()  # Attempt to stop it if it didn't become ready
        return False

    def stop_server(self) -> None:
        """Send a shutdown request to MCP server and waits for it to terminate."""
        if not self.is_server_running():
            logger.info("MCP server is not running.")
            return

        logger.info("Attempting to shut down MCP server gracefully...")
        try:
            response = requests.post(self.shutdown_url, timeout=5)
            if response.status_code == 200:
                logger.info("Shutdown request sent successfully to MCP server.")
            else:
                logger.warning(
                    f"Failed to send shutdown request. Status: {response.status_code}"
                )
        except requests.RequestException:
            logger.exception("Error sending shutdown request to MCP server")

        if self.server_thread and self.server_thread.is_alive():
            logger.info("Waiting for MCP server thread to terminate...")
            self.server_thread.join(timeout=10)  # Give it some time to shut down
            if self.server_thread.is_alive():
                logger.warning(
                    "MCP server thread did not terminate gracefully. Forcing shutdown."
                )
                if self.server_process and self.server_process.poll() is None:
                    self.server_process.terminate()
                    self.server_process.wait(timeout=5)
                    if self.server_process.poll() is None:
                        self.server_process.kill()
        self.server_thread = None
        self.server_process = None
        logger.info("MCP server stopped.")

    def is_server_running(self) -> bool:
        """Check if the MCP server thread is alive and its process is running."""
        if self.server_thread and self.server_thread.is_alive():
            if self.server_process and self.server_process.poll() is None:
                return True
            else:
                logger.warning(
                    "Server thread is alive but process is not. Cleaning up."
                )
                self.server_thread = None
                self.server_process = None
                return False
        return False
