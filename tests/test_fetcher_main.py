"""Tests for the main public methods of the PackageSourceFetcher class.

This file focuses on the orchestration logic of the `fetch` method,
mocking the lower-level helper methods that are already tested in
`test_fetcher.py`.
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.fetcher import PackageSourceFetcher


@pytest.fixture
def fetcher_instance(tmp_path: Path, mocker: MockerFixture) -> PackageSourceFetcher:
    """Provide a PackageSourceFetcher instance with a temp base path.

    It also mocks the initial check for an existing directory, assuming it's empty
    by default, so we can test the fetching logic.
    """
    package_info = {"name": "test-package", "version": "1.0.0"}
    fetcher = PackageSourceFetcher(
        base_save_path=str(tmp_path), package_info_dict=package_info
    )
    # Mock the 'exists' method on the Path class, not the instance, to avoid
    # the 'read-only' attribute error.
    mocker.patch("pathlib.Path.exists", return_value=False)
    return fetcher


def test_fetch_succeeds_if_already_exists(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify `fetch` succeeds immediately if the directory has content."""
    # Arrange
    # Override the mock from the fixture to simulate an existing, non-empty directory.
    mocker.patch("pathlib.Path.exists", return_value=True)
    # Mock iterdir to make `any()` return True for the check.
    mocker.patch("pathlib.Path.iterdir", return_value=[Path("a_file.txt")])

    # Mock the helper functions that are called in this specific branch
    mock_cleanup_git = mocker.patch.object(
        fetcher_instance, "_cleanup_git_dir_from_path"
    )
    mock_fetch_pypi = mocker.patch.object(fetcher_instance, "_fetch_from_pypi")
    mock_get_vcs = mocker.patch.object(fetcher_instance, "_get_vcs_url")

    # Act
    success, is_master, path = fetcher_instance.fetch()

    # Assert
    assert success is True
    assert path == str(fetcher_instance.download_target_path)
    mock_cleanup_git.assert_called_once_with(fetcher_instance.download_target_path)
    # No fetching methods should be called
    mock_fetch_pypi.assert_not_called()
    mock_get_vcs.assert_not_called()


def test_fetch_succeeds_with_pypi_sdist(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify `fetch` calls the PyPI method first and succeeds."""
    # Arrange
    mock_fetch_pypi = mocker.patch.object(
        fetcher_instance, "_fetch_from_pypi", return_value=True
    )
    mock_get_vcs = mocker.patch.object(fetcher_instance, "_get_vcs_url")

    # Act
    success, is_master, path = fetcher_instance.fetch()

    # Assert
    assert success is True
    assert is_master is False
    assert path == str(fetcher_instance.download_target_path)
    mock_fetch_pypi.assert_called_once()
    mock_get_vcs.assert_not_called()


def test_fetch_falls_back_to_vcs_tag(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify `fetch` falls back to VCS tag clone if PyPI fails."""
    # Arrange
    mocker.patch.object(fetcher_instance, "_fetch_from_pypi", return_value=False)
    mocker.patch.object(
        fetcher_instance,
        "_get_vcs_url",
        return_value="https://github.com/test/repo.git",
    )
    mock_fetch_tag = mocker.patch.object(
        fetcher_instance, "_fetch_from_vcs_tag", return_value=True
    )
    mock_fetch_main = mocker.patch.object(fetcher_instance, "_fetch_from_vcs_main")

    # Act
    success, is_master, path = fetcher_instance.fetch()

    # Assert
    assert success is True
    assert is_master is False
    assert path == str(fetcher_instance.download_target_path)
    mock_fetch_tag.assert_called_once_with("https://github.com/test/repo.git")
    mock_fetch_main.assert_not_called()


def test_fetch_falls_back_to_vcs_main(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify `fetch` falls back to VCS main branch if PyPI and tag fail."""
    # Arrange
    mocker.patch.object(fetcher_instance, "_fetch_from_pypi", return_value=False)
    mocker.patch.object(
        fetcher_instance,
        "_get_vcs_url",
        return_value="https://github.com/test/repo.git",
    )
    mocker.patch.object(fetcher_instance, "_fetch_from_vcs_tag", return_value=False)
    mock_fetch_main = mocker.patch.object(
        fetcher_instance, "_fetch_from_vcs_main", return_value=True
    )

    # Act
    success, is_master, path = fetcher_instance.fetch()

    # Assert
    assert success is True
    assert is_master is True
    assert path == str(fetcher_instance.download_target_path)
    mock_fetch_main.assert_called_once_with("https://github.com/test/repo.git")


def test_fetch_fails_if_all_methods_fail(
    fetcher_instance: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify `fetch` fails gracefully if all fetch methods fail."""
    # Arrange
    mocker.patch.object(fetcher_instance, "_fetch_from_pypi", return_value=False)
    mocker.patch.object(fetcher_instance, "_get_vcs_url", return_value=None)
    mock_fetch_tag = mocker.patch.object(fetcher_instance, "_fetch_from_vcs_tag")
    mock_fetch_main = mocker.patch.object(fetcher_instance, "_fetch_from_vcs_main")
    # Also mock the final cleanup that happens on failure
    mock_cleanup = mocker.patch.object(fetcher_instance, "_cleanup_target_dir_content")

    # Act
    success, is_master, path = fetcher_instance.fetch()

    # Assert
    assert success is False
    assert is_master is False
    assert path is None
    mock_fetch_tag.assert_not_called()
    mock_fetch_main.assert_not_called()
    mock_cleanup.assert_called_once()
