"""app paths module."""

import logging
import os
from pathlib import Path

import platformdirs

from devildex.info import APPLICATION_AUTHOR, APPLICATION_NAME

logger = logging.getLogger(__name__)


class AppPaths:
    """Handle i paths standard per i file di dati, configuration.

    cache e log dell application in modo independent dalla platform.
    """

    def __init__(
        self,
        app_name: str = APPLICATION_NAME,
        app_author: str = APPLICATION_AUTHOR,
        version: str | None = None,
    ) -> None:
        """Initialize i paths.

        Args:
            app_name: Il nome dell application.
            app_author: author/organization del application.
            version: Una version optional of app, per paths versioned.

        """
        self._dirs = platformdirs.PlatformDirs(
            appname=app_name, appauthor=app_author, version=version
        )

    @property
    def user_data_dir(self) -> Path:
        """Directory per i file di dati del user."""
        path = Path(self._dirs.user_data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def user_config_dir(self) -> Path:
        """Directory per i file di configuration del user."""
        path = Path(self._dirs.user_config_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def user_cache_dir(self) -> Path:
        """Directory per i file di cache."""
        path = Path(self._dirs.user_cache_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def user_log_dir(self) -> Path:
        """Directory for user-specific log files."""
        path = Path(self._dirs.user_log_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def docsets_base_dir(self) -> Path:
        """Directory base default per i docset generated.

        Usually si found inside della user_data_dir.
        """
        path = self.user_data_dir / "docsets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Path:
        """Path per il file del database dell application.

        May be un file SQLite, ad example.
        """
        return self.user_data_dir / "devildex.db"

    @property
    def settings_file_path(self) -> Path:
        """Path per il file delle settings del application."""
        return self.user_config_dir / "settings.toml"

    @property
    def active_project_registry_dir(self) -> Path:
        """Directory where the active project registration file is stored."""
        path = self.user_data_dir / ACTIVE_PROJECT_REGISTRY_SUBDIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def active_project_file(self) -> Path:
        """Path for the file that reports the active project at startup.

        This file is created by the "Companion" process, read by DevildexCore
        And then deleted by DevildexApp.OnInit if tried successfully.
        """
        return self.active_project_registry_dir / ACTIVE_PROJECT_REGISTRATION_FILENAME

    @property
    def devildex_ini_path(self) -> Path:
        """Path for the devildex.ini configuration file."""
        if os.getenv("DEVILDEX_DEV_MODE") == "1":
            # In dev mode, look in the project root
            return Path("devildex.ini")
        else:
            # Otherwise, use the user's config directory
            return self.user_config_dir / "devildex.ini"


if __name__ == "__main__":
    paths = AppPaths()
    logger.info(f"User Data Directory:     {paths.user_data_dir}")
    logger.info(f"User Config Directory:   {paths.user_config_dir}")
    logger.info(f"User Cache Directory:    {paths.user_cache_dir}")
    logger.info(f"User Log Directory:      {paths.user_log_dir}")
    logger.info(f"Docsets Base Directory:  {paths.docsets_base_dir}")
    logger.info(f"Database Path:           {paths.database_path}")
    logger.info(f"Settings File Path:      {paths.settings_file_path}")
ACTIVE_PROJECT_REGISTRY_SUBDIR = "registered_projects"
ACTIVE_PROJECT_REGISTRATION_FILENAME = "current_registered_project.json"
