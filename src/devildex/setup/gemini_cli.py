"""Setup script to configure Gemini CLI for the DevilDex MCP Server.

This script is platform-independent and safely merges the DevilDex MCP server
configuration into the user's existing Gemini CLI settings.

It intelligently detects the Gemini configuration directory from a list of
known locations.
"""

import json
import logging
import os
import platform
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)

DEVILDEX_CONFIG_FILE = "devildex.mcp.json"
GEMINI_APP_NAME = "gemini"


def find_gemini_settings_path() -> Path:
    """Intelligently finds the path to settings.json by checking known locations.

    It checks for existing directories in order of likelihood. If none are found,
    it defaults to the most common path for npm-based installations.

    Returns:
        A Path object pointing to the determined settings.json file.

    """
    home = Path.home()

    potential_dirs = []

    system = platform.system()
    if system == "Windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            potential_dirs.append(Path(appdata) / GEMINI_APP_NAME)
    elif system == "Darwin":
        potential_dirs.append(
            home / "Library" / "Application Support" / GEMINI_APP_NAME
        )
    else:
        potential_dirs.append(home / ".config" / GEMINI_APP_NAME)

    potential_dirs.insert(0, home / f".{GEMINI_APP_NAME}")

    for config_dir in potential_dirs:
        if config_dir.is_dir():
            logger.info(f"Found existing Gemini config directory: {config_dir}")
            return config_dir / "settings.json"

    logger.info("No existing Gemini config directory found. Defaulting to npm-style.")
    default_path = home / f".{GEMINI_APP_NAME}"
    return default_path / "settings.json"


def main() -> None:
    """Launch the main execution function."""
    logger.info("--- DevilDex MCP Server Setup for Gemini CLI ---")

    try:
        devildex_config_path = resources.files("devildex.setup").joinpath(
            DEVILDEX_CONFIG_FILE
        )
    except Exception as e:
        logger.exception(
            f"\nERROR: Could not locate config file '{DEVILDEX_CONFIG_FILE}'. Reason:",
            exc_info=e,
        )
        return

    if not devildex_config_path.is_file():
        logger.error(
            f"\nERROR: Config file '{DEVILDEX_CONFIG_FILE}' not found at expected path."
        )
        return

    logger.info(f"Found DevilDex config: {devildex_config_path}")

    try:
        gemini_settings_path = find_gemini_settings_path()
    except Exception as e:
        logger.exception(
            "\nERROR: Could not determine Gemini CLI config path.", exc_info=e
        )
        return

    logger.info(f"Targeting Gemini CLI settings file: {gemini_settings_path}")

    settings_data = {}
    if gemini_settings_path.is_file():
        logger.info("Found existing settings.json, reading...")
        with open(gemini_settings_path, encoding="utf-8") as f:
            try:
                settings_data = json.load(f)
            except json.JSONDecodeError:
                logger.warning("WARNING: settings.json is corrupted. Starting fresh.")
    else:
        logger.info("No existing settings.json found. A new one will be created.")

    with open(devildex_config_path, encoding="utf-8") as f:
        devildex_data = json.load(f)

    if "mcpServers" not in settings_data:
        settings_data["mcpServers"] = {}

    if "mcpServers" in devildex_data:
        settings_data["mcpServers"].update(devildex_data["mcpServers"])
        logger.info("Merging DevilDex MCP server configuration...")

    try:
        gemini_settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gemini_settings_path, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=2)
        logger.info("\nSuccessfully updated Gemini CLI configuration!")
        logger.info(f"Configuration written to: {gemini_settings_path}")
        logger.info("You can now run `gemini` and use the tools provided by DevilDex.")

    except OSError as e:
        logger.exception("\nERROR: Failed to write to settings file.", exc_info=e)
        logger.exception("Please check file permissions.")


if __name__ == "__main__":
    main()
