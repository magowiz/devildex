"""Tests for the PackageSourceFetcher class and its utility functions."""

import json
import sys
from pathlib import Path

import pytest
import requests
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


# --- Tests for _cleanup_target_dir_content ---


def test_cleanup_target_dir_content_success(fetcher_instance: PackageSourceFetcher):
    """Verify it removes all files and subdirectories from the target directory."""
    # Arrange
    target_dir = fetcher_instance.download_target_path
    target_dir.mkdir(parents=True, exist_ok=True)

    # Create some content to be deleted
    (target_dir / "file_to_delete.txt").touch()
    subdir = target_dir / "subdir_to_delete"
    subdir.mkdir()
    (subdir / "nested_file.txt").touch()

    # Pre-condition: The directory contains items
    assert any(target_dir.iterdir())

    # Act
    fetcher_instance._cleanup_target_dir_content()

    # Assert
    # Post-condition: The directory itself should still exist, but be empty.
    assert target_dir.exists()
    assert not any(target_dir.iterdir())


def test_cleanup_target_dir_content_handles_os_error(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify it handles an OSError during cleanup without crashing."""
    # Arrange
    target_dir = fetcher_instance.download_target_path
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "a_file.txt").touch()  # Add a file
    (target_dir / "a_subdir").mkdir()  # Add a directory

    # Mock shutil.rmtree to fail, simulating a permissions error on a subdirectory
    mocker.patch("shutil.rmtree", side_effect=OSError("Permission denied"))

    # Act & Assert
    # The method should catch the exception and log it, not crash.
    # So, we just call it and expect no exception to be raised.
    try:
        fetcher_instance._cleanup_target_dir_content()
    except OSError:
        pytest.fail(
            "The _cleanup_target_dir_content method raised an unhandled OSError."
        )


# --- Tests for _is_valid_vcs_url ---

vcs_url_test_cases = [
    ("https://github.com/user/repo.git", True),
    ("http://gitlab.com/user/repo", True),
    ("https://bitbucket.org/user/repo", True),
    ("git@github.com:user/repo.git", True),
    ("https://example.com/not-a-vcs", False),
    ("just_a_string", False),
    ("", False),
    (None, False),
]


@pytest.mark.parametrize("url, expected", vcs_url_test_cases)
def test_is_valid_vcs_url(url, expected):
    """Verify VCS URL validation for various inputs."""
    assert PackageSourceFetcher._is_valid_vcs_url(url) is expected


# --- Security Tests for Archive Extraction ---


def test_is_path_safe_allows_paths_within_base(tmp_path: Path):
    """Verify _is_path_safe correctly identifies paths inside the base directory."""
    base_dir = tmp_path.resolve()
    safe_path1 = base_dir / "file.txt"
    safe_path2 = base_dir / "subdir" / "another_file.txt"
    assert PackageSourceFetcher._is_path_safe(base_dir, safe_path1) is True
    assert PackageSourceFetcher._is_path_safe(base_dir, safe_path2) is True
    assert PackageSourceFetcher._is_path_safe(base_dir, base_dir) is True


def test_is_path_safe_rejects_paths_outside_base(tmp_path: Path):
    """Verify _is_path_safe rejects paths that resolve outside the base directory."""
    base_dir = tmp_path.resolve()
    # Path traversal attempt
    unsafe_path1 = base_dir / ".." / "outside_file.txt"
    # Absolute path outside the base
    unsafe_path2 = Path("/etc/passwd")

    assert PackageSourceFetcher._is_path_safe(base_dir, unsafe_path1) is False
    assert PackageSourceFetcher._is_path_safe(base_dir, unsafe_path2) is False


@pytest.mark.parametrize(
    "member_name, expected",
    [
        # Standard safe cases
        ("file.txt", True),
        ("subdir/file.txt", True),
        ("subdir/deeper/file.txt", True),
        # Unsafe path traversal
        ("../evil.txt", False),
        ("subdir/../../evil.txt", False),
        # Unsafe absolute paths (POSIX style)
        ("/absolute/path.txt", False),
        # Platform-dependent check for Windows-style absolute paths
        # This path is UNSAFE (is_absolute() -> True) only on Windows.
        # On Linux/macOS, it's a valid relative filename, so it's SAFE.
        ("C:\\windows\\system32", sys.platform != "win32"),
    ],
)
def test_is_member_name_safe(member_name, expected):
    """Verify _is_member_name_safe correctly identifies safe and unsafe archive member names."""
    assert PackageSourceFetcher._is_member_name_safe(member_name) is expected


# --- Tests for _find_vcs_url_in_dict ---

find_vcs_url_test_cases = [
    (None, "none", None),
    ({}, "empty", None),
    (
        {"Source Code": "https://github.com/user/repo.git"},
        "source_code",
        "https://github.com/user/repo.git",
    ),
    (
        {"Source": "https://gitlab.com/user/repo"},
        "source",
        "https://gitlab.com/user/repo",
    ),
    (
        {"Repository": "https://bitbucket.org/user/repo"},
        "repository",
        "https://bitbucket.org/user/repo",
    ),
    (
        {"Homepage": "https://github.com/user/homepage.git"},
        "homepage",
        "https://github.com/user/homepage.git",
    ),
    ({"Homepage": "https://example.com/docs"}, "non_vcs_homepage", None),
    ({"Documentation": "https://docs.example.com"}, "docs_only", None),
    (
        {
            "Homepage": "https://github.com/user/homepage.git",
            "Source Code": "https://github.com/user/repo.git",
        },
        "priority",
        "https://github.com/user/repo.git",
    ),
    ({"Source Code": "https://not-a-vcs.com/repo"}, "invalid_vcs_url", None),
]


@pytest.mark.parametrize(
    "urls_dict, case_id, expected_url",
    find_vcs_url_test_cases,
    ids=[c[1] for c in find_vcs_url_test_cases],
)
def test_find_vcs_url_in_dict(
    fetcher_instance: PackageSourceFetcher, urls_dict, case_id, expected_url
):
    """Verify that _find_vcs_url_in_dict correctly identifies the best VCS URL."""
    # The 'source_description' argument is only for logging, so we use a dummy value.
    found_url = fetcher_instance._find_vcs_url_in_dict(urls_dict, "test_source")
    assert found_url == expected_url


# --- Tests for _get_vcs_url ---


def test_get_vcs_url_uses_local_url_first(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify _get_vcs_url returns a local URL without calling PyPI if one is valid."""
    # Arrange
    fetcher_instance.project_urls = {"Source Code": "https://github.com/local/repo.git"}
    mock_fetch_from_pypi = mocker.patch.object(
        fetcher_instance, "_fetch_project_urls_from_pypi"
    )

    # Act
    found_url = fetcher_instance._get_vcs_url()

    # Assert
    assert found_url == "https://github.com/local/repo.git"
    mock_fetch_from_pypi.assert_not_called()


def test_get_vcs_url_falls_back_to_pypi(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify _get_vcs_url calls PyPI when no local URL is valid."""
    # Arrange
    fetcher_instance.project_urls = {"Homepage": "https://not-a-vcs.com"}
    mock_fetch_from_pypi = mocker.patch.object(
        fetcher_instance,
        "_fetch_project_urls_from_pypi",
        return_value={"Repository": "https://github.com/pypi/repo.git"},
    )

    # Act
    found_url = fetcher_instance._get_vcs_url()

    # Assert
    assert found_url == "https://github.com/pypi/repo.git"
    mock_fetch_from_pypi.assert_called_once()


def test_get_vcs_url_returns_none_if_no_url_found(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify _get_vcs_url returns None if no valid URL is found anywhere."""
    # Arrange
    fetcher_instance.project_urls = {}  # No local URLs
    mock_fetch_from_pypi = mocker.patch.object(
        fetcher_instance, "_fetch_project_urls_from_pypi", return_value=None
    )

    # Act
    found_url = fetcher_instance._get_vcs_url()

    # Assert
    assert found_url is None
    mock_fetch_from_pypi.assert_called_once()


def test_get_vcs_url_caches_result(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify that after the first call, the result is cached and not re-calculated."""
    # Arrange
    fetcher_instance.project_urls = {}
    mock_fetch_from_pypi = mocker.patch.object(
        fetcher_instance,
        "_fetch_project_urls_from_pypi",
        return_value={"Source": "https://github.com/cached/repo.git"},
    )

    # Act
    first_call_url = fetcher_instance._get_vcs_url()
    second_call_url = fetcher_instance._get_vcs_url()  # This should hit the cache

    # Assert
    assert first_call_url == "https://github.com/cached/repo.git"
    assert second_call_url == first_call_url
    # The expensive network call should only happen once
    mock_fetch_from_pypi.assert_called_once()


# --- Tests for _fetch_project_urls_from_pypi ---


def test_fetch_from_pypi_success(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify it returns the correct dict on a successful API call."""
    # Arrange
    expected_urls = {"Homepage": "http://example.com"}
    mock_response = mocker.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"info": {"project_urls": expected_urls}}
    mocker.patch("requests.get", return_value=mock_response)

    # Act
    result = fetcher_instance._fetch_project_urls_from_pypi()

    # Assert
    assert result == expected_urls


def test_fetch_from_pypi_request_exception(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify it returns None when a network error occurs."""
    # Arrange
    mocker.patch("requests.get", side_effect=requests.RequestException("Network Error"))

    # Act
    result = fetcher_instance._fetch_project_urls_from_pypi()

    # Assert
    assert result is None


def test_fetch_from_pypi_bad_json(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify it returns None when the API response is not valid JSON."""
    # Arrange
    mock_response = mocker.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
    mocker.patch("requests.get", return_value=mock_response)

    # Act
    result = fetcher_instance._fetch_project_urls_from_pypi()

    # Assert
    assert result is None


def test_fetch_from_pypi_missing_keys(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
):
    """Verify it returns None if the JSON response is missing expected keys."""
    # Arrange
    mock_response = mocker.Mock()
    mock_response.raise_for_status.return_value = None
    # Simulate a valid JSON response, but without the 'project_urls' key
    mock_response.json.return_value = {"info": {"version": "1.0.0"}}
    mocker.patch("requests.get", return_value=mock_response)

    # Act
    result = fetcher_instance._fetch_project_urls_from_pypi()

    # Assert
    assert result is None
