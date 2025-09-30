"""Tests for the PackageSourceFetcher module."""

import shutil
import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from devildex.fetcher import MissingPackageInfoError, PackageSourceFetcher


@pytest.fixture
def fetcher_instance(tmp_path: Path) -> PackageSourceFetcher:
    """Provide a standard PackageSourceFetcher instance for tests."""
    package_info = {
        "name": "my-package",
        "version": "1.2.3",
        "project_urls": {"Source": "https://github.com/user/my-package.git"},
    }
    return PackageSourceFetcher(
        base_save_path=str(tmp_path), package_info_dict=package_info
    )


def test_init_missing_info(tmp_path: Path) -> None:
    """Verify that MissingPackageInfoError is raised if name or version are missing."""
    with pytest.raises(MissingPackageInfoError):
        PackageSourceFetcher(
            base_save_path=str(tmp_path), package_info_dict={"name": "only-name"}
        )
    with pytest.raises(MissingPackageInfoError):
        PackageSourceFetcher(
            base_save_path=str(tmp_path), package_info_dict={"version": "only-version"}
        )


def test_cleanup_target_dir_content_not_exists(
    fetcher_instance: PackageSourceFetcher,
) -> None:
    """Verify cleanup does nothing if the target directory doesn't exist."""
    assert not fetcher_instance.download_target_path.exists()
    fetcher_instance._cleanup_target_dir_content()


@patch("devildex.fetcher.requests.get")
def test_fetch_from_pypi_success(
    mock_get: MagicMock, fetcher_instance: PackageSourceFetcher, mocker: MagicMock
) -> None:
    """Verify successful fetch from PyPI."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "urls": [{"packagetype": "sdist", "url": "https://example.com/sdist.tar.gz"}]
    }
    mock_get.return_value = mock_response
    mocker.patch.object(
        fetcher_instance, "_download_and_extract_archive", return_value=True
    )
    result = fetcher_instance._fetch_from_pypi()
    assert result is True
    fetcher_instance._download_and_extract_archive.assert_called_once_with(
        "https://example.com/sdist.tar.gz", mocker.ANY, from_vcs=False
    )


@patch("devildex.fetcher.requests.get")
def test_fetch_from_pypi_no_sdist(
    mock_get: MagicMock, fetcher_instance: PackageSourceFetcher
) -> None:
    """Verify fetch from PyPI fails if no sdist URL is found."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"urls": [{"packagetype": "wheel", "url": "..."}]}
    mock_get.return_value = mock_response
    result = fetcher_instance._fetch_from_pypi()
    assert result is False


@patch(
    "devildex.fetcher.requests.get",
    side_effect=requests.RequestException("Network Error"),
)
def test_fetch_from_pypi_network_error(
    mock_get: MagicMock, fetcher_instance: PackageSourceFetcher
) -> None:
    """Verify fetch from PyPI fails gracefully on a network error."""
    result = fetcher_instance._fetch_from_pypi()
    assert result is False


def create_test_zip(path: Path, content_dir_name: str, file_name: str) -> Path:
    """Create a test zip file."""
    zip_path = path / "test.zip"
    content_path = path / content_dir_name / file_name
    content_path.parent.mkdir()
    content_path.write_text("hello")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(content_path, arcname=f"{content_dir_name}/{file_name}")
    return zip_path


def test_download_and_extract_zip_archive(
    fetcher_instance: PackageSourceFetcher, tmp_path: Path, mocker: MagicMock
) -> None:
    """Verify the full download and extract process for a zip file."""
    test_zip_path = create_test_zip(tmp_path, "my-package-1.2.3", "main.py")
    mocker.patch(
        "devildex.fetcher.PackageSourceFetcher._download_file",
        side_effect=lambda filename, url, **kwargs: shutil.copy(
            test_zip_path, filename
        ),
    )
    temp_base_dir = tmp_path / "temp_download"
    success = fetcher_instance._download_and_extract_archive(
        "https://example.com/test.zip", temp_base_dir, from_vcs=True
    )
    assert success is True
    final_content_path = fetcher_instance.download_target_path / "main.py"
    assert final_content_path.exists()
    assert final_content_path.read_text() == "hello"
    assert not temp_base_dir.exists()


@patch("devildex.fetcher.shutil.which", return_value="/usr/bin/git")
@patch("devildex.fetcher.subprocess.run")
def test_try_fetch_tag_shallow_clone_success(
    mock_run: MagicMock,
    mock_which: MagicMock,
    fetcher_instance: PackageSourceFetcher,
    mocker: MagicMock,
) -> None:
    """Verify a successful shallow clone of a tag."""
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
    mocker.patch.object(
        fetcher_instance, "_cleanup_git_dir_from_path", return_value=True
    )
    repo_url = "https://github.com/user/my-package.git"
    tag = "v1.2.3"
    result = fetcher_instance._try_fetch_tag_shallow_clone(repo_url, [tag])
    assert result is True
    mock_run.assert_called_once_with(
        [
            "/usr/bin/git",
            "clone",
            "--depth",
            "1",
            "--branch",
            tag,
            repo_url,
            str(fetcher_instance.download_target_path),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=None,
        encoding="utf-8",
        errors="replace",
    )
    fetcher_instance._cleanup_git_dir_from_path.assert_called_once()


@patch("devildex.fetcher.shutil.which", return_value=None)
def test_run_git_command_git_not_found(
    mock_which: MagicMock, fetcher_instance: PackageSourceFetcher
) -> None:
    """Verify that git command fails if git executable is not found."""
    result = fetcher_instance._run_git_command(["git", "status"])
    assert result is None


def test_fetch_main_flow_pypi_first(
    fetcher_instance: PackageSourceFetcher, mocker: MagicMock
) -> None:
    """Test the main fetch() orchestration, succeeding with PyPI."""
    mocker.patch.object(fetcher_instance, "_fetch_from_pypi", return_value=True)
    mocker.patch.object(fetcher_instance, "_get_vcs_url")
    success, is_master, path = fetcher_instance.fetch()
    assert success is True
    assert is_master is False
    assert path == str(fetcher_instance.download_target_path)
    fetcher_instance._fetch_from_pypi.assert_called_once()
    fetcher_instance._get_vcs_url.assert_not_called()


def test_fetch_main_flow_fallback_to_vcs_tag(
    fetcher_instance: PackageSourceFetcher, mocker: MagicMock
) -> None:
    """Test the main fetch() orchestration, falling back to VCS tag."""
    mocker.patch.object(fetcher_instance, "_fetch_from_pypi", return_value=False)
    mocker.patch.object(
        fetcher_instance,
        "_get_vcs_url",
        return_value="https://github.com/user/my-package.git",
    )
    mocker.patch.object(fetcher_instance, "_fetch_from_vcs_tag", return_value=True)
    mocker.patch.object(fetcher_instance, "_fetch_from_vcs_main")
    success, is_master, path = fetcher_instance.fetch()
    assert success is True
    assert is_master is False
    assert path == str(fetcher_instance.download_target_path)
    fetcher_instance._fetch_from_pypi.assert_called_once()
    fetcher_instance._get_vcs_url.assert_called_once()
    fetcher_instance._fetch_from_vcs_tag.assert_called_once()
    fetcher_instance._fetch_from_vcs_main.assert_not_called()


def test_fetch_main_flow_fallback_to_vcs_main(
    fetcher_instance: PackageSourceFetcher, mocker: MagicMock
) -> None:
    """Test the main fetch() orchestration, falling back to VCS main branch."""
    mocker.patch.object(fetcher_instance, "_fetch_from_pypi", return_value=False)
    mocker.patch.object(
        fetcher_instance,
        "_get_vcs_url",
        return_value="https://github.com/user/my-package.git",
    )
    mocker.patch.object(fetcher_instance, "_fetch_from_vcs_tag", return_value=False)
    mocker.patch.object(fetcher_instance, "_fetch_from_vcs_main", return_value=True)
    success, is_master, path = fetcher_instance.fetch()
    assert success is True
    assert is_master is True
    assert path == str(fetcher_instance.download_target_path)
    fetcher_instance._fetch_from_vcs_main.assert_called_once()


def test_fetch_main_flow_all_fail(
    fetcher_instance: PackageSourceFetcher, mocker: MagicMock
) -> None:
    """Test the main fetch() orchestration where all methods fail."""
    mocker.patch.object(fetcher_instance, "_fetch_from_pypi", return_value=False)
    mocker.patch.object(
        fetcher_instance,
        "_get_vcs_url",
        return_value="https://github.com/user/my-package.git",
    )
    mocker.patch.object(fetcher_instance, "_fetch_from_vcs_tag", return_value=False)
    mocker.patch.object(fetcher_instance, "_fetch_from_vcs_main", return_value=False)
    mocker.patch.object(fetcher_instance, "_cleanup_target_dir_content")
    success, is_master, path = fetcher_instance.fetch()
    assert success is False
    assert is_master is False
    assert path is None
    fetcher_instance._cleanup_target_dir_content.assert_called_once()
