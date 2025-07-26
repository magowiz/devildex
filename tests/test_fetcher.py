"""Tests for the PackageSourceFetcher class and its utility functions."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.fetcher import PackageSourceFetcher

# --- Tests for _sanitize_path_component ---

# A list of tuples: (input_name, expected_sanitized_name)
sanitize_test_cases = [
    ("normal-package-name", "normal-package-name"),
    ("package with spaces", "package_with_spaces"),
    ('invalid/\\:char*?"<>|s', "invalid_char_s"),
    ("multiple___underscores", "multiple_underscores"),
    ("_leading_and_trailing_", "leading_and_trailing"),
    ("", "unknown_component"),
    (None, "unknown_component"),
    ("___", "sanitized_empty_component"),
]


@pytest.mark.parametrize("input_name, expected", sanitize_test_cases)
def test_sanitize_path_component(input_name, expected):
    """Verify path component sanitization for various inputs."""
    # This is a static method, so we can call it directly on the class
    # without needing an instance.
    sanitized_name = PackageSourceFetcher._sanitize_path_component(input_name)
    assert sanitized_name == expected


@pytest.fixture
def fetcher_instance(tmp_path: Path) -> PackageSourceFetcher:
    """Provides a PackageSourceFetcher instance with a temporary base path."""
    package_info = {"name": "test-package", "version": "1.0.0"}
    return PackageSourceFetcher(
        base_save_path=str(tmp_path), package_info_dict=package_info
    )


# --- Tests for _ensure_target_dir_exists ---


def test_ensure_target_dir_exists_success(
    fetcher_instance: PackageSourceFetcher,
):
    """Verify it creates the directory and returns True on success."""
    # Arrange
    target_dir = fetcher_instance.download_target_path
    # Pre-condition: The directory should not exist before the call
    assert not target_dir.exists()

    # Act
    result = fetcher_instance._ensure_target_dir_exists()

    # Assert
    # Post-condition: The method should return True and the directory should exist
    assert result is True
    assert target_dir.is_dir()


def test_ensure_target_dir_exists_os_error(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify it returns False when directory creation fails with an OSError."""
    # Arrange
    # We patch the class method to raise an OSError when called.
    mocker.patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied"))

    # Act
    result = fetcher_instance._ensure_target_dir_exists()

    # Assert
    assert result is False
