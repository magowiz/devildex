"""Tests for the VCS fallback mechanisms in PackageSourceFetcher.

This file focuses on unit testing the individual methods responsible for
fetching source code from Version Control Systems, such as:
- _try_fetch_tag_github_archive
- _try_fetch_tag_shallow_clone
- _try_fetch_tag_full_clone_checkout

These tests will use mocking to isolate the logic of each method.
"""

from pathlib import Path
from unittest.mock import call

import pytest
from pytest_mock import MockerFixture

from devildex.fetcher import PackageSourceFetcher


@pytest.fixture
def fetcher(tmp_path: Path) -> PackageSourceFetcher:
    """Provide a PackageSourceFetcher instance for testing VCS fallbacks."""
    package_info = {
        "name": "vcs-test-pkg",
        "version": "1.2.3",
        "project_urls": {},
    }
    return PackageSourceFetcher(
        base_save_path=str(tmp_path), package_info_dict=package_info
    )




def test_fetch_github_archive_success(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify fetch gitHub archive succeeds if _download_and_extract_archive does."""
    repo_url = "https://github.com/user/repo"
    tag_variations = ["1.2.3", "v1.2.3"]
    expected_url = "https://github.com/user/repo/archive/refs/tags/1.2.3.tar.gz"

    mock_download_extract = mocker.patch.object(
        fetcher, "_download_and_extract_archive", return_value=True
    )

    result = fetcher._try_fetch_tag_github_archive(repo_url, tag_variations)

    assert result is True

    mock_download_extract.assert_called_once()
    assert mock_download_extract.call_args[0][0] == expected_url


def test_fetch_github_archive_falls_back_on_urls(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify it tries multiple URL variations for a tag until one succeeds."""
    # Arrange
    repo_url = "https://github.com/user/repo.git"
    repo_path_segment = "user/repo"
    tag_to_test = "1.2.3"

    # These are the 4 URL formats the method will try for a single tag
    archive_urls_to_try = [
        f"https://github.com/{repo_path_segment}/archive/refs/tags/{tag_to_test}.tar.gz",
        f"https://github.com/{repo_path_segment}/archive/refs/tags/{tag_to_test}.zip",
        f"https://github.com/{repo_path_segment}/archive/{tag_to_test}.tar.gz",
        f"https://github.com/{repo_path_segment}/archive/{tag_to_test}.zip",
    ]

    mock_download_extract = mocker.patch.object(
        fetcher,
        "_download_and_extract_archive",
        side_effect=[False, False, False, True],
    )

    # Act
    result = fetcher._try_fetch_tag_github_archive(repo_url, [tag_to_test])

    # Assert
    assert result is True
    assert mock_download_extract.call_count == 4
    # Check that it was called with all the expected URLs in order
    expected_calls = [
        call(url, mocker.ANY, from_vcs=True) for url in archive_urls_to_try
    ]
    mock_download_extract.assert_has_calls(expected_calls)


def test_fetch_github_archive_all_fail(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify it returns False if all download attempts for all tags fail."""
    repo_url = "https://github.com/user/repo"
    tag_variations = ["1.2.3", "v1.2.3"]
    mock_download_extract = mocker.patch.object(
        fetcher, "_download_and_extract_archive", return_value=False
    )

    result = fetcher._try_fetch_tag_github_archive(repo_url, tag_variations)

    assert result is False
    assert mock_download_extract.call_count == 8


def test_fetch_github_archive_not_a_github_url(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify it returns False immediately if the URL is not from GitHub."""
    repo_url = "https://gitlab.com/user/repo"
    tag_variations = ["1.2.3"]
    mock_download_extract = mocker.patch.object(
        fetcher, "_download_and_extract_archive"
    )

    result = fetcher._try_fetch_tag_github_archive(repo_url, tag_variations)

    assert result is False
    mock_download_extract.assert_not_called()




def test_shallow_clone_success(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify _try_fetch_tag_shallow_clone succeeds and calls git correctly."""
    repo_url = "https://github.com/user/repo.git"
    tag_variations = ["1.2.3", "v1.2.3"]

    mock_run_git = mocker.patch.object(
        fetcher, "_run_git_command", return_value=mocker.Mock(returncode=0)
    )
    mock_cleanup_git = mocker.patch.object(fetcher, "_cleanup_git_dir_from_path")
    mock_ensure_dir = mocker.patch.object(
        fetcher, "_ensure_target_dir_exists", return_value=True
    )

    # Act
    result = fetcher._try_fetch_tag_shallow_clone(repo_url, tag_variations)

    # Assert
    assert result is True
    mock_ensure_dir.assert_called_once()
    mock_run_git.assert_called_once_with(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            "1.2.3",
            repo_url,
            str(fetcher.download_target_path),
        ]
    )
    mock_cleanup_git.assert_called_once_with(fetcher.download_target_path)


def test_shallow_clone_falls_back_on_tags(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify it tries the next tag if the first git clone command fails."""
    repo_url = "https://github.com/user/repo.git"
    tag_variations = ["1.2.3", "v1.2.3"]

    mock_run_git = mocker.patch.object(
        fetcher, "_run_git_command", side_effect=[None, mocker.Mock(returncode=0)]
    )
    mock_cleanup_git = mocker.patch.object(fetcher, "_cleanup_git_dir_from_path")
    mocker.patch.object(fetcher, "_ensure_target_dir_exists", return_value=True)

    result = fetcher._try_fetch_tag_shallow_clone(repo_url, tag_variations)

    assert result is True
    assert mock_run_git.call_count == 2
    first_call_args = mock_run_git.call_args_list[0].args[0]
    second_call_args = mock_run_git.call_args_list[1].args[0]

    assert "1.2.3" in first_call_args
    assert "v1.2.3" in second_call_args

    mock_cleanup_git.assert_called_once_with(fetcher.download_target_path)


def test_shallow_clone_all_fail(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify it returns False if all git clone commands fail."""
    repo_url = "https://github.com/user/repo.git"
    tag_variations = ["1.2.3", "v1.2.3"]

    mock_run_git = mocker.patch.object(fetcher, "_run_git_command", return_value=None)
    mocker.patch.object(fetcher, "_ensure_target_dir_exists", return_value=True)
    mock_cleanup_git = mocker.patch.object(fetcher, "_cleanup_git_dir_from_path")

    result = fetcher._try_fetch_tag_shallow_clone(repo_url, tag_variations)

    assert result is False
    assert mock_run_git.call_count == 2
    mock_cleanup_git.assert_not_called()


def test_shallow_clone_dir_creation_fails(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify it returns False if it cannot create the target directory."""
    # Arrange
    repo_url = "https://github.com/user/repo.git"
    tag_variations = ["1.2.3"]

    mock_run_git = mocker.patch.object(fetcher, "_run_git_command")
    # Simulate failure to create directory
    mocker.patch.object(fetcher, "_ensure_target_dir_exists", return_value=False)

    # Act
    result = fetcher._try_fetch_tag_shallow_clone(repo_url, tag_variations)

    # Assert
    assert result is False
    mock_run_git.assert_not_called()


# --- Tests for _try_fetch_tag_full_clone_checkout ---


def test_full_clone_checkout_success(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify the full clone and checkout process succeeds."""
    repo_url = "https://github.com/user/repo.git"
    tag_variations = ["1.2.3"]
    temp_clone_dir = fetcher.base_save_path / "vcs-test-pkg_temp_dl" / "full_clone"

    mock_git_clone = mocker.Mock(returncode=0)
    mock_git_checkout = mocker.Mock(returncode=0)
    mock_run_git = mocker.patch.object(
        fetcher, "_run_git_command", side_effect=[mock_git_clone, mock_git_checkout]
    )

    mock_copy = mocker.patch.object(fetcher, "_copy_cloned_content", return_value=True)
    mock_rmtree = mocker.patch("shutil.rmtree")
    mocker.patch.object(fetcher, "_ensure_target_dir_exists", return_value=True)
    mocker.patch("pathlib.Path.exists", return_value=True)

    result = fetcher._try_fetch_tag_full_clone_checkout(repo_url, tag_variations)

    assert result is True

    clone_call = mock_run_git.call_args_list[0]
    assert clone_call.args[0] == ["git", "clone", repo_url, str(temp_clone_dir)]

    # Verify checkout was called correctly
    checkout_call = mock_run_git.call_args_list[1]
    assert checkout_call.args[0] == [
        "git",
        "-C",
        str(temp_clone_dir),
        "checkout",
        "1.2.3",
    ]

    mock_copy.assert_called_once_with(temp_clone_dir, fetcher.download_target_path)
    mock_rmtree.assert_called_with(temp_clone_dir)


def test_full_clone_fails(fetcher: PackageSourceFetcher, mocker: MockerFixture) -> None:
    """Verify the process fails if the initial git clone fails."""
    repo_url = "https://github.com/user/repo.git"
    tag_variations = ["1.2.3"]

    mocker.patch.object(fetcher, "_run_git_command", return_value=None)
    mock_rmtree = mocker.patch("shutil.rmtree")

    result = fetcher._try_fetch_tag_full_clone_checkout(repo_url, tag_variations)

    assert result is False
    mock_rmtree.assert_not_called()


def test_full_clone_checkout_fails(
    fetcher: PackageSourceFetcher, mocker: MockerFixture
) -> None:
    """Verify the process fails if checkout fails for all tags."""
    repo_url = "https://github.com/user/repo.git"
    tag_variations = ["1.2.3", "v1.2.3"]
    temp_clone_dir = fetcher.base_save_path / "vcs-test-pkg_temp_dl" / "full_clone"

    mock_git_clone = mocker.Mock(returncode=0)
    mock_git_checkout_fail = mocker.Mock(returncode=1)
    mocker.patch.object(
        fetcher,
        "_run_git_command",
        side_effect=[mock_git_clone, mock_git_checkout_fail, mock_git_checkout_fail],
    )

    mock_copy = mocker.patch.object(fetcher, "_copy_cloned_content")
    mock_rmtree = mocker.patch("shutil.rmtree")
    # Mock path.exists() to ensure cleanup logic is triggered
    mocker.patch("pathlib.Path.exists", return_value=True)

    # Act
    result = fetcher._try_fetch_tag_full_clone_checkout(repo_url, tag_variations)

    # Assert
    assert result is False
    mock_copy.assert_not_called()
    # Cleanup should still happen
    mock_rmtree.assert_called_with(temp_clone_dir)
