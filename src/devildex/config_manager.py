"""config manager module."""

import configparser
import logging
from pathlib import Path
from typing import Optional, Self

from devildex.app_paths import AppPaths

logger = logging.getLogger(__name__)


class ConfigManager:
    """Config manager class."""

    _instance = None
    _config: Optional[configparser.ConfigParser] = None
    _config_path: Optional[Path] = None

    def __new__(cls) -> Self:
        """Singleton implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self.app_paths = AppPaths()
        self._config_path = self.app_paths.devildex_ini_path
        self._load_config()

    def _load_config(self) -> None:
        self._config = configparser.ConfigParser()
        if self._config_path and self._config_path.exists():
            try:
                self._config.read(self._config_path)
                logger.info(f"Loaded configuration from: {self._config_path}")
            except configparser.Error:
                logger.exception(
                    f"Error reading configuration file {self._config_path}"
                )
                self._config = configparser.ConfigParser()
        else:
            logger.info(
                f"Configuration file not found at: {self._config_path}."
                " Creating with default settings."
            )
            self._config.add_section("mcp_server_dev")
            self._config.set("mcp_server_dev", "enabled", "false")
            self._config.set("mcp_server_dev", "hide_gui_when_enabled", "false")
            if self._config_path:
                try:
                    self._config_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self._config_path, "w") as configfile:
                        self._config.write(configfile)
                    logger.info(
                        f"Created default configuration file at: {self._config_path}"
                    )
                except OSError:
                    logger.exception(
                        "Error creating default configuration file"
                        f" {self._config_path}"
                    )

    def get_mcp_server_enabled(self) -> bool:
        """Get mcp server enabled setting."""
        return self._config.getboolean("mcp_server_dev", "enabled", fallback=False)

    def get_mcp_server_hide_gui_when_enabled(self) -> bool:
        """Get mcp server hide gui when enabled setting."""
        return self._config.getboolean(
            "mcp_server_dev", "hide_gui_when_enabled", fallback=False
        )

    def get_mcp_server_port(self) -> int:
        """Get mcp server port setting."""
        return self._config.getint("mcp_server_dev", "port", fallback=8001)

    def set_mcp_server_enabled(self, value: bool) -> None:
        """Set mcp server enabled setting."""
        self._config.set("mcp_server_dev", "enabled", str(value))

    def set_mcp_server_hide_gui_when_enabled(self, value: bool) -> None:
        """Set mcp server hide gui when enabled setting."""
        self._config.set("mcp_server_dev", "hide_gui_when_enabled", str(value))

    def set_mcp_server_port(self, value: int) -> None:
        """Set mcp server port setting."""
        self._config.set("mcp_server_dev", "port", str(value))

    def save_config(self) -> None:
        """Save the configuration to the file."""
        if self._config_path:
            try:
                logger.debug(
                    f"Attempting to save config. Current _config state: {self._config}"
                )
                with open(self._config_path, "w") as configfile:
                    self._config.write(configfile)
                logger.info(f"Configuration saved to: {self._config_path}")
            except OSError:
                logger.exception(f"Error saving configuration file {self._config_path}")
        else:
            logger.error("Cannot save configuration: _config_path is not set.")


if __name__ == "__main__":

    config = ConfigManager()
