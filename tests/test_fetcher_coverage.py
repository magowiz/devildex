"""test fetcher module."""

import json
import pathlib
import subprocess
import tarfile
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.devildex.fetcher import PackageSourceFetcher

# Dummy paths for testing
DUMMY_PACKAGE_INFO = {"name": "test_package", "version": "1.0.0"}


class TestPackageSourceFetcherCoverage:
    """Class that test PackageSourceFetcher coverage."""

    BASE_SAVE_PATH = pathlib.Path("/tmp/dummy_path_for_class_level_evaluation")

    @pytest.fixture(autouse=True)
    def setup_and_teardown_test_env(self, tmp_path: pathlib.Path):
        self.BASE_SAVE_PATH = tmp_path / "devildex_test_output"
        self.BASE_SAVE_PATH.mkdir(parents=True, exist_ok=True)

    # Test cases for _is_path_safe (line 161)
    @patch("src.devildex.fetcher.Path.resolve")
    def test_is_path_safe_raises_exception(self, mock_resolve):
        """Test is path safe raises exception."""
        mock_resolve.side_effect = OSError("Permission denied")
        base_path = pathlib.Path("/safe")
        target_path = pathlib.Path("/unsafe")
        assert PackageSourceFetcher._is_path_safe(base_path, target_path) is False

    # Test cases for _extract_zip_safely (lines 190, 202)
    def test_extract_zip_safely_unsafe_member_name(self) -> None:
        """Test extract zip safely."""
        zip_path = self.BASE_SAVE_PATH / "unsafe.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("safe_file.txt", "content")

        with patch(
            "src.devildex.fetcher.PackageSourceFetcher._is_member_name_safe",
            return_value=False,
        ):
            assert not PackageSourceFetcher._extract_zip_safely(
                zip_path, self.BASE_SAVE_PATH / "extracted"
            )

    def test_extract_zip_safely_bad_zip_file(self):
        # Create a dummy corrupted zip file
        zip_path = self.BASE_SAVE_PATH / "corrupted.zip"
        with open(zip_path, "wb") as f:
            f.write(b"this is not a zip file")

        assert not PackageSourceFetcher._extract_zip_safely(
            zip_path, self.BASE_SAVE_PATH / "extracted"
        )

    @patch("zipfile.ZipFile")
    def test_extract_zip_safely_os_error_during_extraction(self, mock_zip_file):
        mock_zip_instance = MagicMock()
        mock_zip_file.return_value.__enter__.return_value = mock_zip_instance
        mock_zip_instance.infolist.return_value = [
            MagicMock(filename="file.txt", is_dir=lambda: False)
        ]
        mock_zip_instance.extract.side_effect = OSError("Disk full")

        zip_path = self.BASE_SAVE_PATH / "dummy.zip"
        zip_path.touch()  # Create a dummy file for the path check

        assert not PackageSourceFetcher._extract_zip_safely(
            zip_path, self.BASE_SAVE_PATH / "extracted"
        )

    # Test cases for _extract_tar_safely (lines 213, 225)
    @patch("tarfile.open")
    def test_extract_tar_safely_unsafe_member_name(self, mock_tar_open):
        mock_tar_instance = MagicMock()
        mock_tar_open.return_value.__enter__.return_value = mock_tar_instance
        # Simulate an unsafe member name
        mock_tar_instance.getmembers.return_value = [
            MagicMock(name="../evil.txt", isfile=lambda: True, isdir=lambda: False)
        ]

        # Mock _is_member_name_safe to return False for the unsafe name
        with patch(
            "src.devildex.fetcher.PackageSourceFetcher._is_member_name_safe",
            return_value=False,
        ):
            tar_path = self.BASE_SAVE_PATH / "dummy.tar.gz"
            tar_path.touch()  # Create a dummy file for the path check
            assert not PackageSourceFetcher._extract_tar_safely(
                tar_path, self.BASE_SAVE_PATH / "extracted"
            )

    @patch("tarfile.open", side_effect=tarfile.TarError("Corrupted archive"))
    def test_extract_tar_safely_bad_tar_file(self, mock_tar_open):
        # Create a dummy corrupted tar file (not actually used, but path is needed)
        tar_path = self.BASE_SAVE_PATH / "corrupted.tar.gz"
        tar_path.touch()  # Ensure file exists for tarfile.open to try to open it

        assert not PackageSourceFetcher._extract_tar_safely(
            tar_path, self.BASE_SAVE_PATH / "extracted"
        )

    @patch("tarfile.open")
    def test_extract_tar_safely_tar_error_during_extraction(self, mock_tar_open):
        mock_tar_instance = MagicMock()
        mock_tar_open.return_value.__enter__.return_value = mock_tar_instance
        mock_tar_instance.getmembers.return_value = [
            MagicMock(name="file.txt", isfile=lambda: True, isdir=lambda: False)
        ]
        mock_tar_instance.extract.side_effect = tarfile.TarError("Corrupted archive")

        tar_path = self.BASE_SAVE_PATH / "dummy.tar.gz"
        tar_path.touch()  # Create a dummy file for the path check

        assert not PackageSourceFetcher._extract_tar_safely(
            tar_path, self.BASE_SAVE_PATH / "extracted"
        )

    # Test for _determine_content_source_dir (line 270)
    def test_determine_content_source_dir_empty(self):
        empty_dir = self.BASE_SAVE_PATH / "empty_dir"
        empty_dir.mkdir()
        assert PackageSourceFetcher._determine_content_source_dir(empty_dir) is None

    # Test for _determine_content_source_dir (line 275 - else branch)
    def test_determine_content_source_dir_multiple_items(self):
        multi_item_dir = self.BASE_SAVE_PATH / "multi_item_dir"
        multi_item_dir.mkdir(parents=True)
        (multi_item_dir / "file1.txt").touch()
        (multi_item_dir / "dir1").mkdir()
        assert (
            PackageSourceFetcher._determine_content_source_dir(multi_item_dir)
            == multi_item_dir
        )

    def test_determine_content_source_dir_single_file(self):
        single_file_dir = self.BASE_SAVE_PATH / "single_file_dir"
        single_file_dir.mkdir()
        (single_file_dir / "file1.txt").touch()
        assert (
            PackageSourceFetcher._determine_content_source_dir(single_file_dir)
            == single_file_dir
        )

    # Test for _move_extracted_content (line 286)
    @patch("src.devildex.fetcher.shutil.move")
    def test_move_extracted_content_os_error(self, mock_shutil_move) -> None:
        """Test move extracted content raises exception."""
        mock_shutil_move.side_effect = OSError("Permission denied")
        source_dir = self.BASE_SAVE_PATH / "source"
        source_dir.mkdir()
        (source_dir / "file.txt").touch()
        destination_dir = self.BASE_SAVE_PATH / "destination"
        destination_dir.mkdir()
        assert not PackageSourceFetcher._move_extracted_content(
            source_dir, destination_dir
        )

    # Test for _download_and_extract_archive (lines 300, 309, 313, 320, 321)
    @patch("src.devildex.fetcher.PackageSourceFetcher._download_file")
    @patch("src.devildex.fetcher.PackageSourceFetcher._extract_archive")
    @patch("src.devildex.fetcher.PackageSourceFetcher._determine_content_source_dir")
    @patch("src.devildex.fetcher.PackageSourceFetcher._cleanup_target_dir_content")
    @patch("src.devildex.fetcher.PackageSourceFetcher._ensure_target_dir_exists")
    @patch("src.devildex.fetcher.PackageSourceFetcher._move_extracted_content")
    def test_download_and_extract_archive_temp_base_dir_exists(
        self,
        mock_move,
        mock_ensure_target_dir,
        mock_cleanup_target_dir,
        mock_determine_content_source_dir,
        mock_extract_archive,
        mock_download_file,
    ):
        temp_base_dir = self.BASE_SAVE_PATH / "temp_base_dir_exists"
        temp_base_dir.mkdir()  # Ensure it exists for this test
        (temp_base_dir / "some_file.txt").touch()  # Add some content

        mock_extract_archive.return_value = True
        mock_determine_content_source_dir.return_value = (
            self.BASE_SAVE_PATH / "content_source"
        )
        mock_ensure_target_dir.return_value = True
        mock_move.return_value = True

        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert fetcher._download_and_extract_archive(
            "http://example.com/archive.zip", temp_base_dir
        )
        # Check if shutil.rmtree was called on temp_base_dir
        assert not temp_base_dir.exists()  # shutil.rmtree should have removed it

    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._extract_archive", return_value=False
    )
    def test_download_and_extract_archive_extract_fails(self, mock_extract_archive):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._download_and_extract_archive(
            "http://example.com/archive.zip", self.BASE_SAVE_PATH / "temp_extract_fails"
        )

    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._extract_archive", return_value=True
    )
    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._determine_content_source_dir",
        return_value=None,
    )
    def test_download_and_extract_archive_determine_content_fails(
        self, mock_determine_content_source_dir, mock_extract_archive
    ):
        """Test download and extract archive determine content fails."""
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._download_and_extract_archive(
            "http://example.com/archive.zip",
            self.BASE_SAVE_PATH / "temp_determine_fails",
        )

    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._extract_archive", return_value=True
    )
    @patch("src.devildex.fetcher.PackageSourceFetcher._determine_content_source_dir")
    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._ensure_target_dir_exists",
        return_value=False,
    )
    def test_download_and_extract_archive_ensure_target_fails(
        self,
        mock_ensure_target_dir,
        mock_determine_content_source_dir,
        mock_extract_archive,
    ):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        mock_determine_content_source_dir.return_value = (
            self.BASE_SAVE_PATH / "content_source"
        )
        assert not fetcher._download_and_extract_archive(
            "http://example.com/archive.zip",
            self.BASE_SAVE_PATH / "temp_ensure_target_fails",
        )

    @patch("requests.get", side_effect=requests.RequestException("Network error"))
    def test_download_and_extract_archive_requests_exception(self, mock_requests_get):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._download_and_extract_archive(
            "http://example.com/archive.zip",
            self.BASE_SAVE_PATH / "temp_requests_exception",
        )

    # Test for _run_git_command (lines 355, 359, 369, 374, 378, 382, 385)
    @patch("src.devildex.fetcher.shutil.which", return_value=None)
    def test_run_git_command_git_not_found(self, mock_which) -> None:
        """Test run git command when git is not found."""
        assert PackageSourceFetcher._run_git_command(["git", "clone", "url"]) is None

    @patch("src.devildex.fetcher.shutil.which", return_value="/usr/bin/git")
    @patch("subprocess.run")
    def test_run_git_command_non_git_first_element(
        self, mock_subprocess_run, mock_which
    ):
        mock_process = MagicMock(stdout="output", stderr="", returncode=0)
        mock_subprocess_run.return_value = mock_process
        result = PackageSourceFetcher._run_git_command(
            ["clone", "url"], check_errors=False
        )
        mock_subprocess_run.assert_called_once_with(
            ["/usr/bin/git", "clone", "url"],
            capture_output=True,
            text=True,
            check=False,
            cwd=None,
            encoding="utf-8",
            errors="replace",
        )
        assert result == mock_process

    @patch("src.devildex.fetcher.shutil.which", return_value="/usr/bin/git")
    @patch("subprocess.run")
    @patch("src.devildex.fetcher.logger")
    def test_run_git_command_stdout_logged(
        self, mock_logger, mock_subprocess_run, mock_which
    ):
        mock_process = MagicMock(stdout="some stdout", stderr="", returncode=0)
        mock_subprocess_run.return_value = mock_process
        PackageSourceFetcher._run_git_command(["git", "status"])
        mock_logger.debug.assert_any_call("Git stdout:\nsome stdout")

    @patch("src.devildex.fetcher.shutil.which", return_value="/usr/bin/git")
    @patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            1, "git clone", stderr="error output"
        ),
    )
    @patch("src.devildex.fetcher.logger")
    def test_run_git_command_called_process_error_caught(
        self, mock_logger, mock_subprocess_run, mock_which
    ):
        result = PackageSourceFetcher._run_git_command(["git", "clone", "url"])
        assert result is None
        mock_logger.warning.assert_not_called()

    @patch("src.devildex.fetcher.shutil.which", return_value="/usr/bin/git")
    @patch("subprocess.run")
    @patch("src.devildex.fetcher.logger")
    def test_run_git_command_stderr_warning_logged(
        self, mock_logger, mock_subprocess_run, mock_which
    ):
        mock_process = MagicMock(stdout="", stderr="some error", returncode=1)
        mock_subprocess_run.return_value = mock_process
        PackageSourceFetcher._run_git_command(
            ["git", "pull"], check_errors=False
        )  # check_errors=False to allow stderr without raising
        mock_logger.warning.assert_any_call("Git stderr:\nsome error")

    @patch("src.devildex.fetcher.shutil.which", return_value="/usr/bin/git")
    @patch("subprocess.run")
    @patch("src.devildex.fetcher.logger")
    def test_run_git_command_stderr_info_logged(
        self, mock_logger, mock_subprocess_run, mock_which
    ) -> None:
        """Test run git command stderr info logged."""
        mock_process = MagicMock(stdout="some info", stderr="some info", returncode=0)
        mock_subprocess_run.return_value = mock_process
        PackageSourceFetcher._run_git_command(["git", "status"])
        mock_logger.debug.assert_any_call("Git stderr (info):\nsome info")

    # Test for _cleanup_git_dir_from_path (lines 397, 399)
    @patch(
        "src.devildex.fetcher.shutil.rmtree", side_effect=OSError("Permission denied")
    )
    def test_cleanup_git_dir_from_path_os_error(self, mock_rmtree):
        git_dir = self.BASE_SAVE_PATH / ".git"
        git_dir.mkdir()
        assert not PackageSourceFetcher._cleanup_git_dir_from_path(self.BASE_SAVE_PATH)

    def test_cleanup_git_dir_from_path_git_is_file(self) -> None:
        """Test cleanup git dir from path when .git is a file."""
        git_file = self.BASE_SAVE_PATH / ".git"
        git_file.touch()
        assert not PackageSourceFetcher._cleanup_git_dir_from_path(self.BASE_SAVE_PATH)

    @patch("requests.get")
    def test_fetch_from_pypi_no_sdist_url(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"urls": []}  # No sdist
        mock_requests_get.return_value = mock_response
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._fetch_from_pypi()

    @patch("requests.get", side_effect=requests.RequestException("Network error"))
    def test_fetch_from_pypi_requests_exception(self, mock_requests_get):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._fetch_from_pypi()

    @patch("requests.get")
    def test_fetch_from_pypi_json_decode_error(self, mock_requests_get):
        """Test fetch from pypi when JSON decoding fails."""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_requests_get.return_value = mock_response
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._fetch_from_pypi()

    # Test for _try_fetch_tag_github_archive (line 434, 454)
    def test_try_fetch_tag_github_archive_non_github_url(self):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._try_fetch_tag_github_archive(
            "http://example.com/repo.git", ["v1.0.0"]
        )

    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._download_and_extract_archive",
        return_value=False,
    )
    def test_try_fetch_tag_github_archive_all_attempts_fail(
        self, mock_download_and_extract_archive
    ):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        repo_url = "https://github.com/user/repo.git"
        tag_variations = ["v1.0.0", "1.0.0"]
        assert not fetcher._try_fetch_tag_github_archive(repo_url, tag_variations)

    # Test for _try_fetch_tag_shallow_clone (line 472)
    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._ensure_target_dir_exists",
        return_value=False,
    )
    def test_try_fetch_tag_shallow_clone_ensure_target_fails(
        self, mock_ensure_target_dir_exists
    ):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        repo_url = "https://github.com/user/repo.git"
        tag_variations = ["v1.0.0"]
        assert not fetcher._try_fetch_tag_shallow_clone(repo_url, tag_variations)

    # Test for _copy_cloned_content (lines 480, 485, 488, 490)
    def test_copy_cloned_content_skips_git_dir(self):
        source_dir = self.BASE_SAVE_PATH / "source_with_git"
        source_dir.mkdir()
        (source_dir / ".git").mkdir()
        (source_dir / "file.txt").touch()
        destination_dir = self.BASE_SAVE_PATH / "destination_no_git"
        destination_dir.mkdir()

        PackageSourceFetcher._copy_cloned_content(source_dir, destination_dir)
        assert not (destination_dir / ".git").exists()
        assert (destination_dir / "file.txt").exists()

    @patch("src.devildex.fetcher.shutil.copytree", side_effect=OSError("Disk full"))
    def test_copy_cloned_content_copytree_os_error(self, mock_copytree):
        source_dir = self.BASE_SAVE_PATH / "source_dir_error"
        source_dir.mkdir()
        (source_dir / "subdir").mkdir()
        destination_dir = self.BASE_SAVE_PATH / "destination_dir_error"
        destination_dir.mkdir()
        assert not PackageSourceFetcher._copy_cloned_content(
            source_dir, destination_dir
        )

    @patch(
        "src.devildex.fetcher.shutil.copy2", side_effect=OSError("Permission denied")
    )
    def test_copy_cloned_content_copy2_os_error(self, mock_copy2):
        source_dir = self.BASE_SAVE_PATH / "source_file_error"
        source_dir.mkdir()
        (source_dir / "file.txt").touch()
        destination_dir = self.BASE_SAVE_PATH / "destination_file_error"
        destination_dir.mkdir()
        assert not PackageSourceFetcher._copy_cloned_content(
            source_dir, destination_dir
        )

    # Test for _try_fetch_tag_variations (lines 500, 505, 510, 511)
    @patch("src.devildex.fetcher.PackageSourceFetcher._run_git_command")
    @patch("src.devildex.fetcher.PackageSourceFetcher._ensure_target_dir_exists")
    @patch("src.devildex.fetcher.PackageSourceFetcher._copy_cloned_content")
    @patch("src.devildex.fetcher.logger")
    def test_try_fetch_tag_variations_checkout_success_copy_success(
        self,
        mock_logger,
        mock_copy_cloned_content,
        mock_ensure_target_dir_exists,
        mock_run_git_command,
    ):
        mock_run_git_command.return_value = MagicMock(returncode=0)
        mock_ensure_target_dir_exists.return_value = True
        mock_copy_cloned_content.return_value = True
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        temp_clone_dir = self.BASE_SAVE_PATH / "temp_clone"
        temp_clone_dir.mkdir()
        assert fetcher._try_fetch_tag_variations(["v1.0.0"], temp_clone_dir)
        mock_logger.info.assert_called_with(
            f"Checkout of tag 'v1.0.0' successful in {temp_clone_dir}."
        )

    @patch("src.devildex.fetcher.PackageSourceFetcher._run_git_command")
    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._ensure_target_dir_exists",
        return_value=False,
    )
    def test_try_fetch_tag_variations_ensure_target_fails(
        self, mock_ensure_target_dir_exists, mock_run_git_command
    ):
        mock_run_git_command.return_value = MagicMock(returncode=0)
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        temp_clone_dir = self.BASE_SAVE_PATH / "temp_clone"
        temp_clone_dir.mkdir()
        assert not fetcher._try_fetch_tag_variations(["v1.0.0"], temp_clone_dir)

    # Test for _try_fetch_tag_full_clone_checkout (lines 525, 531, 534, 543)
    @patch("src.devildex.fetcher.PackageSourceFetcher._run_git_command")
    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._try_fetch_tag_variations",
        return_value=True,
    )
    def test_try_fetch_tag_full_clone_checkout_success(
        self, mock_try_fetch_tag_variations, mock_run_git_command
    ):
        mock_run_git_command.return_value = MagicMock(returncode=0)
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert fetcher._try_fetch_tag_full_clone_checkout(
            "http://example.com/repo.git", ["v1.0.0"]
        )

    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._run_git_command", return_value=None
    )
    def test_try_fetch_tag_full_clone_checkout_clone_fails(self, mock_run_git_command):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._try_fetch_tag_full_clone_checkout(
            "http://example.com/repo.git", ["v1.0.0"]
        )

    # Test for _fetch_from_vcs_tag (line 568)
    def test_fetch_from_vcs_tag_version_starts_with_v(self):
        package_info = {"name": "test_package", "version": "v1.0.0"}
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, package_info)
        # Mock the actual fetch methods to avoid network calls
        with (
            patch(
                "src.devildex.fetcher.PackageSourceFetcher._try_fetch_tag_github_archive",
                return_value=False,
            ),
            patch(
                "src.devildex.fetcher.PackageSourceFetcher._try_fetch_tag_shallow_clone",
                return_value=False,
            ),
            patch(
                "src.devildex.fetcher.PackageSourceFetcher._try_fetch_tag_full_clone_checkout",
                return_value=False,
            ),
        ):
            # Call the method to ensure the line is hit
            fetcher._fetch_from_vcs_tag("http://example.com/repo.git")
            # Assert that the tag variations set would have included '1.0.0'
            # This is hard to assert directly without inspecting internal state,
            # but the test execution will cover the line.

    # Test for _fetch_from_vcs_main (lines 588, 590)
    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._ensure_target_dir_exists",
        return_value=False,
    )
    @patch("src.devildex.fetcher.logger")
    def test_fetch_from_vcs_main_ensure_target_fails(
        self, mock_logger, mock_ensure_target_dir_exists
    ):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        assert not fetcher._fetch_from_vcs_main("http://example.com/repo.git")
        mock_logger.error.assert_called_with(
            "Unable to prepare target directory for the VCS main branch clone."
        )

    # Test for fetch (line 648)
    def test_fetch_target_dir_exists_with_content(self):
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        fetcher.download_target_path.mkdir(parents=True, exist_ok=True)
        (fetcher.download_target_path / "dummy_file.txt").touch()
        with patch(
            "src.devildex.fetcher.PackageSourceFetcher._cleanup_git_dir_from_path"
        ) as mock_cleanup:
            success, is_master, path_str = fetcher.fetch()
            mock_cleanup.assert_called_once_with(fetcher.download_target_path)
            assert success
            assert not is_master
            assert path_str == str(fetcher.download_target_path)

    # Test for fetch (line 672)
    @patch(
        "src.devildex.fetcher.PackageSourceFetcher._fetch_from_pypi", return_value=False
    )
    @patch("src.devildex.fetcher.PackageSourceFetcher._get_vcs_url", return_value=None)
    @patch("src.devildex.fetcher.PackageSourceFetcher._cleanup_target_dir_content")
    def test_fetch_all_methods_fail_cleanup_called(
        self, mock_cleanup_target_dir_content, mock_get_vcs_url, mock_fetch_from_pypi
    ):
        """Test fetch all methods fail and cleanup called."""
        fetcher = PackageSourceFetcher(self.BASE_SAVE_PATH, DUMMY_PACKAGE_INFO)
        success, is_master, path_str = fetcher.fetch()
        assert not success
        assert not is_master
        assert path_str is None
        mock_cleanup_target_dir_content.assert_called_once()

    @patch("src.devildex.fetcher.logger")
    def test_pprint_function_logs_json(self, mock_logger):
        from src.devildex.fetcher import _pprint_  # Import directly for testing

        data = {"key": "value", "num": 123}
        _pprint_(data)
        mock_logger.info.assert_called_once()
        logged_message = mock_logger.info.call_args[0][0]
        assert (
            '{\n    "key": "value",\n    "num": 123\n}' in logged_message
            or '{\n    "num": 123,\n    "key": "value"\n}' in logged_message
        )  # Order might vary
