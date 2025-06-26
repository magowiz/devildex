"""Module for a development server with live-reload capabilities."""

import http.server
import logging
import socketserver
import threading
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class LiveReloadServer(socketserver.TCPServer):
    """TCP server that allows immediate address reuse.

    This prevents "Address already in use" errors during rapid restarts.
    """

    allow_reuse_address = True


class LiveReloadHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler for the live server.

    It intercepts calls to /rebuild and serves files from the build directory.
    """

    def __init__(
        self, *args, build_dir: Path, rebuild_callback: Callable[[], None], **kwargs
    ) -> None:
        """Initialize the handler with the build directory and rebuild callback."""
        self.build_dir = build_dir
        self.rebuild_callback = rebuild_callback
        super().__init__(*args, directory=str(self.build_dir), **kwargs)

    def do_GET(self) -> None:
        """Handle GET requests, intercepting the /rebuild endpoint."""
        if self.path == "/rebuild":
            logger.info("Rebuild request received from the browser...")

            rebuild_thread = threading.Thread(target=self.rebuild_callback)
            rebuild_thread.start()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "rebuild_triggered"}')
            return
        super().do_GET()


def start_server(
    build_dir: Path, rebuild_callback: Callable[[], None], port: int = 8000
) -> None:
    """Start the local web server.

    Args:
        build_dir: The directory from which to serve files.
        rebuild_callback: The function to call when a /rebuild request is received.
        port: The port to listen on.

    """

    def handler_factory(*args: object, **kwargs: object) -> LiveReloadHandler:
        """Create Factory for handler instances with custom arguments."""
        return LiveReloadHandler(
            *args,
            build_dir=build_dir,
            rebuild_callback=rebuild_callback,
            **kwargs,
        )

    with LiveReloadServer(("", port), handler_factory) as httpd:
        logger.info(f"Server started at http://localhost:{port}")
        logger.info(f"Serving files from directory: {build_dir}")
        logger.info("Press Ctrl+C to stop the server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("\nServer stopped by user.")
            httpd.shutdown()
