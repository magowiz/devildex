"""
Setup script to configure Gemini CLI for the DevilDex MCP Server.

This script is platform-independent and safely merges the DevilDex MCP server
configuration into the user's existing Gemini CLI settings.

It intelligently detects the Gemini configuration directory from a list of
known locations.
"""

import json
import os
import platform
from pathlib import Path
from importlib import resources

# --- Configuration ---
DEVILDEX_CONFIG_FILE = "devildex.mcp.json"
GEMINI_APP_NAME = "gemini"


def find_gemini_settings_path() -> Path:
    """
    Intelligently finds the path to settings.json by checking known locations.

    It checks for existing directories in order of likelihood. If none are found,
    it defaults to the most common path for npm-based installations.

    Returns:
        A Path object pointing to the determined settings.json file.
    """
    home = Path.home()

    # List of potential parent directories for the Gemini configuration.
    # Ordered by likelihood.
    potential_dirs = []

    # OS-specific paths
    system = platform.system()
    if system == "Windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            potential_dirs.append(Path(appdata) / GEMINI_APP_NAME) # C:\Users\<user>\AppData\Roaming\gemini
    elif system == "Darwin": # macOS
        potential_dirs.append(home / "Library" / "Application Support" / GEMINI_APP_NAME)
    else: # Linux and other Unix-likes
        potential_dirs.append(home / ".config" / GEMINI_APP_NAME) # XDG standard

    # The npm-style path is common across all OSes, so we check it first.
    potential_dirs.insert(0, home / f".{GEMINI_APP_NAME}")

    # Check for the first existing directory
    for config_dir in potential_dirs:
        if config_dir.is_dir():
            print(f"Found existing Gemini config directory: {config_dir}")
            return config_dir / "settings.json"

    # If no directory is found, default to the most likely one (npm-style)
    print("No existing Gemini config directory found. Defaulting to npm-style path.")
    default_path = home / f".{GEMINI_APP_NAME}"
    return default_path / "settings.json"


def main():
    """Main execution function."""
    print("--- DevilDex MCP Server Setup for Gemini CLI ---")

    # --- Step 1: Locate devildex.mcp.json ---
    try:
        devildex_config_path = resources.files("devildex.setup").joinpath(DEVILDEX_CONFIG_FILE)
    except Exception as e:
        print(f"\nERROR: Could not locate the configuration file '{DEVILDEX_CONFIG_FILE}'. Reason: {e}")
        return

    if not devildex_config_path.is_file():
        print(f"\nERROR: Configuration file '{DEVILDEX_CONFIG_FILE}' not found at the expected path.")
        return

    print(f"Found DevilDex config: {devildex_config_path}")

    # --- Step 2: Intelligently find Gemini CLI settings.json path ---
    try:
        gemini_settings_path = find_gemini_settings_path()
    except Exception as e:
        print(f"\nERROR: Could not determine Gemini CLI config path. {e}")
        return

    print(f"Targeting Gemini CLI settings file: {gemini_settings_path}")

    # --- Step 3: Read existing settings or create new ones ---
    settings_data = {}
    if gemini_settings_path.is_file():
        print("Found existing settings.json, reading...")
        with open(gemini_settings_path, "r", encoding="utf-8") as f:
            try:
                settings_data = json.load(f)
            except json.JSONDecodeError:
                print("WARNING: settings.json is corrupted. Starting with a fresh configuration.")
    else:
        print("No existing settings.json found. A new one will be created.")

    # --- Step 4: Read DevilDex config and merge safely ---
    with open(devildex_config_path, "r", encoding="utf-8") as f:
        devildex_data = json.load(f)

    if "mcpServers" not in settings_data:
        settings_data["mcpServers"] = {}
    
    if "mcpServers" in devildex_data:
        settings_data["mcpServers"].update(devildex_data["mcpServers"])
        print("Merging DevilDex MCP server configuration...")

    # --- Step 5: Write the updated configuration back ---
    try:
        gemini_settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gemini_settings_path, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=2)
        print("\nSuccessfully updated Gemini CLI configuration!")
        print(f"Configuration written to: {gemini_settings_path}")
        print("You can now run `gemini` and use the tools provided by DevilDex.")

    except OSError as e:
        print(f"\nERROR: Failed to write to settings file. {e}")
        print("Please check file permissions.")


if __name__ == "__main__":
    main()
