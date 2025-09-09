import configparser
import logging
from pathlib import Path
from typing import Optional

from devildex.app_paths import AppPaths

logger = logging.getLogger(__name__)


class ConfigManager:
    _instance = None
    _config: Optional[configparser.ConfigParser] = None
    _config_path: Optional[Path] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.app_paths = AppPaths()
        self._config_path = self.app_paths.devildex_ini_path
        self._load_config()

    def _load_config(self):
        self._config = configparser.ConfigParser()
        if self._config_path and self._config_path.exists():
            try:
                self._config.read(self._config_path)
                logger.info(f"Loaded configuration from: {self._config_path}")
            except configparser.Error as e:
                logger.error(
                    f"Error reading configuration file {self._config_path}: {e}"
                )
                self._config = configparser.ConfigParser()  # Reset to empty config
        else:
            logger.info(
                f"Configuration file not found at: {self._config_path}. Creating with default settings."
            )
            # Create the file with default settings
            self._config.add_section("mcp_server_dev")
            self._config.set("mcp_server_dev", "enabled", "false")
            self._config.set("mcp_server_dev", "hide_gui_when_enabled", "false")
            if self._config_path:
                try:
                    self._config_path.parent.mkdir(
                        parents=True, exist_ok=True
                    )  # Ensure parent directory exists
                    with open(self._config_path, "w") as configfile:
                        self._config.write(configfile)
                    logger.info(
                        f"Created default configuration file at: {self._config_path}"
                    )
                except OSError as e:
                    logger.error(
                        f"Error creating default configuration file {self._config_path}: {e}"
                    )

    def get_mcp_server_enabled(self) -> bool:
        return self._config.getboolean("mcp_server_dev", "enabled", fallback=False)

    def get_mcp_server_hide_gui_when_enabled(self) -> bool:
        return self._config.getboolean(
            "mcp_server_dev", "hide_gui_when_enabled", fallback=False
        )

    def get_mcp_server_port(self) -> int:
        return self._config.getint("mcp_server_dev", "port", fallback=8001)

    def set_mcp_server_enabled(self, value: bool) -> None:
        self._config.set("mcp_server_dev", "enabled", str(value))

    def set_mcp_server_hide_gui_when_enabled(self, value: bool) -> None:
        self._config.set("mcp_server_dev", "hide_gui_when_enabled", str(value))

    def set_mcp_server_port(self, value: int) -> None:
        self._config.set("mcp_server_dev", "port", str(value))

    def save_config(self) -> None:
        if self._config_path:
            try:
                logger.debug(
                    f"Attempting to save config. Current _config state: {self._config}"
                )
                with open(self._config_path, "w") as configfile:
                    self._config.write(configfile)
                logger.info(f"Configuration saved to: {self._config_path}")
            except OSError as e:
                logger.error(
                    f"Error saving configuration file {self._config_path}: {e}"
                )
        else:
            logger.error("Cannot save configuration: _config_path is not set.")


# Example usage (for testing/demonstration)
if __name__ == "__main__":
    # Set DEVILDEX_DEV_MODE to '1' to test reading from project root
    # os.environ["DEVILDEX_DEV_MODE"] = "1"
    # Create a dummy devildex.ini in the project root for testing
    # with open("devildex.ini", "w") as f:
    #     f.write("[mcp_server_dev]\n")
    #     f.write("enabled = true\n")
    #     f.write("hide_gui_when_enabled = true\n")

    config = ConfigManager()
    print(f"MCP Server Enabled: {config.get_mcp_server_enabled()}")
    print(f"Hide GUI When Enabled: {config.get_mcp_server_hide_gui_when_enabled()}")

    # Clean up dummy file if created
    # if os.path.exists("devildex.ini"):
    #     os.remove("devildex.ini")
