"""MCP Server Manager module."""

import logging
import os
import subprocess
import sys
import threading
import time
from typing import Optional

import requests


from devildex.config_manager import ConfigManager

SERVER_STARTUP_TIMEOUT_SECONDS = 30

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
        if os.getenv("DEVILDEX_DOCSET_BASE_OUTPUT_PATH"):
            env["DEVILDEX_DOCSET_BASE_OUTPUT_PATH"] = os.getenv(
                "DEVILDEX_DOCSET_BASE_OUTPUT_PATH"
            )

        env["PYTHONPATH"] = (
            os.path.abspath("src") + os.pathsep + env.get("PYTHONPATH", "")
        )

        server_command = [
            sys.executable,
            "src/devildex/mcp_server/server.py",
        ]

        self.server_process = subprocess.Popen(  # noqa: S603
            server_command,
            env=env,
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        def log_output(stream, stream_name):
            if stream:
                for line in iter(stream.readline, ""):
                    logger.info(f"MCP Server ({stream_name}): {line.strip()}")
                stream.close()

        stdout_thread = threading.Thread(
            target=log_output, args=(self.server_process.stdout, "stdout")
        )
        stderr_thread = threading.Thread(
            target=log_output, args=(self.server_process.stderr, "stderr")
        )
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        self.server_process.wait()

        stdout_thread.join()
        stderr_thread.join()

    def start_server(self, db_url: str) -> bool:
        """Start the MCP server in a separate thread and waits for it to be ready."""
        if self.is_server_running():
            logger.info("MCP server is already running.")
            return True

        logger.info("Attempting to start MCP server thread...")
        self.server_thread = threading.Thread(target=self._run_server, args=(db_url,))
        self.server_thread.daemon = True
        self.server_thread.start()

        start_time = time.time()
        while time.time() - start_time < SERVER_STARTUP_TIMEOUT_SECONDS:
            if self.server_process and self.server_process.poll() is not None:
                logger.error("MCP server process terminated unexpectedly.")
                self.stop_server()
                return False
            try:
                response = requests.get(self.health_url, timeout=1)
                if response.status_code == 200:
                    logger.info("MCP server is running and healthy.")
                    return True
            except requests.exceptions.ConnectionError:
                logger.debug("MCP server is not yet available. Retrying...")
            time.sleep(0.5)

        logger.error("MCP server did not become healthy within the timeout period.")
        self.stop_server()
        return False

    def stop_server(self) -> None:
        """Send a shutdown request to MCP server and waits for it to terminate."""
        if not self.is_server_running():
            logger.info("MCP server is not running.")
            return

        logger.info("Attempting to shut down MCP server gracefully...")
        try:
            requests.post(self.shutdown_url, timeout=1)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to send shutdown request to MCP server: {e}")

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=10)
            if self.server_thread.is_alive():
                logger.warning("MCP server thread did not terminate gracefully.")
                if self.server_process and self.server_process.poll() is None:
                    logger.info("Terminating MCP server process...")
                    self.server_process.terminate()
                    self.server_process.wait(timeout=5)
                    if self.server_process.poll() is None:
                        logger.warning("MCP server process did not terminate. Killing...")
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
