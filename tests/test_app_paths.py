"""test app path."""

from pathlib import Path
from unittest.mock import patch

import pytest

from devildex.app_paths import (
    ACTIVE_PROJECT_REGISTRATION_FILENAME,
    ACTIVE_PROJECT_REGISTRY_SUBDIR,
    AppPaths,
)


class TestAppPaths:
    """Test the AppPaths class."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, tmp_path: Path) -> None:
        """Set up mocks for AppPaths."""
        self.tmp_path = tmp_path
        self.mock_platform_dirs_patch = patch("platformdirs.PlatformDirs")
        self.MockPlatformDirs = self.mock_platform_dirs_patch.start()
        self.mock_platform_dirs_instance = self.MockPlatformDirs.return_value

        self.mock_platform_dirs_instance.user_data_dir = str(tmp_path / "user_data")
        self.mock_platform_dirs_instance.user_config_dir = str(tmp_path / "user_config")
        self.mock_platform_dirs_instance.user_cache_dir = str(tmp_path / "user_cache")
        self.mock_platform_dirs_instance.user_log_dir = str(tmp_path / "user_log")

        self.app_paths = AppPaths()

        self.MockPlatformDirs.reset_mock()

        yield

        self.mock_platform_dirs_patch.stop()

    def test_init(self) -> None:
        """Test the initialization of AppPaths."""
        _ = AppPaths(app_name="TestApp", app_author="TestAuthor", version="1.0")
        self.MockPlatformDirs.assert_called_once_with(
            appname="TestApp", appauthor="TestAuthor", version="1.0"
        )

    def test_user_data_dir(self) -> None:
        """Test the user_data_dir property."""
        returned_path = self.app_paths.user_data_dir
        expected_path = self.tmp_path / "user_data"
        assert returned_path == expected_path
        assert returned_path.is_dir()

    def test_user_config_dir(self) -> None:
        """Test the user_config_dir property."""
        returned_path = self.app_paths.user_config_dir
        expected_path = self.tmp_path / "user_config"
        assert returned_path == expected_path
        assert returned_path.is_dir()

    def test_user_cache_dir(self) -> None:
        """Test the user_cache_dir property."""
        returned_path = self.app_paths.user_cache_dir
        expected_path = self.tmp_path / "user_cache"
        assert returned_path == expected_path
        assert returned_path.is_dir()

    def test_user_log_dir(self) -> None:
        """Test the user_log_dir property."""
        returned_path = self.app_paths.user_log_dir
        expected_path = self.tmp_path / "user_log"
        assert returned_path == expected_path
        assert returned_path.is_dir()

    def test_docsets_base_dir(self) -> None:
        """Test the docsets_base_dir property."""
        returned_path = self.app_paths.docsets_base_dir
        expected_path = self.tmp_path / "user_data" / "docsets"
        assert returned_path == expected_path
        assert returned_path.is_dir()

    def test_database_path(self) -> None:
        """Test the database_path property."""
        returned_path = self.app_paths.database_path
        expected_path = self.tmp_path / "user_data" / "devildex.db"
        assert returned_path == expected_path

    def test_settings_file_path(self) -> None:
        """Test the settings_file_path property."""
        returned_path = self.app_paths.settings_file_path
        expected_path = self.tmp_path / "user_config" / "settings.toml"
        assert returned_path == expected_path

    def test_active_project_registry_dir(self) -> None:
        """Test the active_project_registry_dir property."""
        returned_path = self.app_paths.active_project_registry_dir
        expected_path = self.tmp_path / "user_data" / ACTIVE_PROJECT_REGISTRY_SUBDIR
        assert returned_path == expected_path
        assert returned_path.is_dir()

    def test_active_project_file(self) -> None:
        """Test the active_project_file property."""
        returned_path = self.app_paths.active_project_file
        expected_path = (
            self.tmp_path
            / "user_data"
            / ACTIVE_PROJECT_REGISTRY_SUBDIR
            / ACTIVE_PROJECT_REGISTRATION_FILENAME
        )
        assert returned_path == expected_path
