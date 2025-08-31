import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from devildex.readthedocs.readthedocs_api import download_readthedocs_prebuilt_robust
from devildex.readthedocs.readthedocs_src import (
    _attempt_single_branch_clone,
    CloneAttemptStatus,
    _cleanup,
    run_clone,
    find_doc_source_in_clone,
    _find_doc_dir_in_repo,
    _find_sphinx_doc_requirements_file,
    build_sphinx_docs,
    _extract_repo_url_branch,
)


@patch("devildex.readthedocs.readthedocs_api.logger.error")
def test_download_readthedocs_prebuilt_robust_empty_project_slug(
    mock_logger_error,
) -> None:
    """Verify download_readthedocs_prebuilt_robust handles empty project_slug."""
    result = download_readthedocs_prebuilt_robust(project_name="")
    assert result is None
    mock_logger_error.assert_called_once_with(
        "Error: project_slug is empty. Cannot proceed with download."
    )


def test_get_vcs_executable_bzr_found(mocker) -> None:
    """Verify _get_vcs_executable returns bzr path when found."""
    mocker.patch("shutil.which", return_value="/usr/bin/bzr")
    assert _get_vcs_executable(True) == "/usr/bin/bzr"


def test_get_vcs_executable_bzr_not_found(mocker, caplog) -> None:
    """Verify _get_vcs_executable logs error when bzr not found."""
    mocker.patch("shutil.which", return_value=None)
    with caplog.at_level(logging.ERROR):
        assert _get_vcs_executable(True) is None
    assert "Error: 'bzr' command not found." in caplog.text


def test_attempt_single_branch_clone_success(mocker, tmp_path: Path) -> None:
    """Verify successful clone attempt."""
    mock_subprocess_run = mocker.patch(
        "subprocess.run", return_value=MagicMock(returncode=0)
    )
    clone_dir = tmp_path / "repo"

    status = _attempt_single_branch_clone(
        "http://repo.git", "main", clone_dir, False, "/usr/bin/git"
    )

    assert status == CloneAttemptStatus.SUCCESS
    mock_subprocess_run.assert_called_once()


def test_attempt_single_branch_clone_failed_retryable(
    mocker, tmp_path: Path, caplog
) -> None:
    """Verify failed clone attempt (retryable)."""
    mock_subprocess_run = mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="clone failed"),
    )
    clone_dir = tmp_path / "repo"

    with caplog.at_level(logging.WARNING):
        status = _attempt_single_branch_clone(
            "http://repo.git", "main", clone_dir, False, "/usr/bin/git"
        )

    assert status == CloneAttemptStatus.FAILED_RETRYABLE
    assert "Failed to clone branch 'main'." in caplog.text


def test_attempt_single_branch_clone_failed_critical_prepare_dir(
    mocker, tmp_path: Path, caplog
) -> None:
    """Verify failed clone attempt due to directory preparation error."""
    mocker.patch("shutil.rmtree", side_effect=OSError("Permission denied"))
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()

    with caplog.at_level(logging.ERROR):
        status = _attempt_single_branch_clone(
            "http://repo.git", "main", clone_dir, False, "/usr/bin/git"
        )

    assert status == CloneAttemptStatus.FAILED_CRITICAL_PREPARE_DIR
    assert "Failed to clean up existing clone directory" in caplog.text


def test_attempt_single_branch_clone_failed_critical_vcs_not_found_exec(
    mocker, tmp_path: Path, caplog
) -> None:
    """Verify failed clone attempt due to VCS executable not found during subprocess.run."""
    mocker.patch("subprocess.run", side_effect=FileNotFoundError("git not found"))
    clone_dir = tmp_path / "repo"

    with caplog.at_level(logging.ERROR):
        status = _attempt_single_branch_clone(
            "http://repo.git", "main", clone_dir, False, "/usr/bin/git"
        )

    assert status == CloneAttemptStatus.FAILED_CRITICAL_VCS_NOT_FOUND_EXEC
    assert (
        "Error: VCS command (/usr/bin/git) not found during subprocess.run."
        in caplog.text
    )


def test_cleanup_existing_dir(tmp_path: Path) -> None:
    """Verify _cleanup removes an existing directory."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    (test_dir / "file.txt").touch()

    _cleanup(test_dir)

    assert not test_dir.exists()


def test_cleanup_non_existent_dir(tmp_path: Path) -> None:
    """Verify _cleanup handles non-existent directory gracefully."""
    non_existent_dir = tmp_path / "non_existent_dir"

    _cleanup(non_existent_dir)

    assert not non_existent_dir.exists()


def test_cleanup_os_error(tmp_path: Path, mocker, caplog) -> None:
    """Verify _cleanup handles OSError during rmtree."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    mocker.patch("shutil.rmtree", side_effect=OSError("Permission denied"))

    with caplog.at_level(logging.ERROR):
        _cleanup(test_dir)

    assert "Error during deleting della repository cloned" in caplog.text


def test_run_clone_success(mocker, tmp_path: Path) -> None:
    """Verify run_clone successfully clones a branch."""
    mock_attempt_single_branch_clone = mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_single_branch_clone",
        return_value=CloneAttemptStatus.SUCCESS,
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_vcs_executable",
        return_value="/usr/bin/git",
    )

    clone_dir = tmp_path / "repo"
    result = run_clone("http://repo.git", "main", clone_dir, False)

    assert result == "main"
    mock_attempt_single_branch_clone.assert_called_once()


def test_run_clone_all_attempts_fail(mocker, tmp_path: Path, caplog) -> None:
    """Verify run_clone returns None when all attempts fail."""
    mock_attempt_single_branch_clone = mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_single_branch_clone",
        return_value=CloneAttemptStatus.FAILED_RETRYABLE,
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_vcs_executable",
        return_value="/usr/bin/git",
    )

    clone_dir = tmp_path / "repo"
    with caplog.at_level(logging.ERROR):
        result = run_clone("http://repo.git", "main", clone_dir, False)

    assert result is None
    assert "Failed to clone any of the attempted branches" in caplog.text


def test_find_doc_source_in_clone_success(tmp_path: Path) -> None:
    """Verify find_doc_source_in_clone finds the doc source."""
    repo_path = tmp_path / "my_repo"
    repo_path.mkdir()
    docs_dir = repo_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "conf.py").touch()

    result = find_doc_source_in_clone(repo_path)

    assert result == str(docs_dir)


def test_find_doc_source_in_clone_not_found(tmp_path: Path, caplog) -> None:
    """Verify find_doc_source_in_clone returns None if doc source not found."""
    repo_path = tmp_path / "my_repo"
    repo_path.mkdir()

    with caplog.at_level(logging.ERROR):
        result = find_doc_source_in_clone(repo_path)

    assert result is None
    assert (
        "No documentation source directory with conf.py found in the clone."
        in caplog.text
    )


def test_find_doc_dir_in_repo_success(tmp_path: Path) -> None:
    """Verify _find_doc_dir_in_repo finds conf.py in a potential doc directory."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    docs_dir = repo_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "conf.py").touch()

    result = _find_doc_dir_in_repo(str(repo_path), ["docs"])

    assert result == str(docs_dir)


def test_find_doc_dir_in_repo_no_conf_py(tmp_path: Path, caplog) -> None:
    """Verify _find_doc_dir_in_repo logs warning if doc dir exists but no conf.py."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    docs_dir = repo_path / "docs"
    docs_dir.mkdir()

    with caplog.at_level(logging.WARNING):
        result = _find_doc_dir_in_repo(str(repo_path), ["docs"])

    assert result is None
    assert f"Found directory '{docs_dir}', but no conf.py." in caplog.text


def test_find_doc_dir_in_repo_root_conf_py(tmp_path: Path) -> None:
    """Verify _find_doc_dir_in_repo finds conf.py in the repository root."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "conf.py").touch()

    result = _find_doc_dir_in_repo(str(repo_path), ["docs"])

    assert result == str(repo_path)


def test_find_doc_dir_in_repo_recursive_search(tmp_path: Path) -> None:
    """Verify _find_doc_dir_in_repo finds conf.py via recursive search."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subdir = repo_path / "src" / "my_project" / "docs"
    subdir.mkdir(parents=True)
    (subdir / "conf.py").touch()

    result = _find_doc_dir_in_repo(str(repo_path), ["non_existent"])

    assert result == str(subdir)


def test_find_doc_dir_in_repo_no_doc_found(tmp_path: Path) -> None:
    """Verify _find_doc_dir_in_repo returns None if no conf.py is found anywhere."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    result = _find_doc_dir_in_repo(str(repo_path), ["docs"])

    assert result is None


def test_find_sphinx_doc_requirements_file_success(tmp_path: Path) -> None:
    """Verify _find_sphinx_doc_requirements_file finds a requirements file."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "requirements.txt").touch()

    result = _find_sphinx_doc_requirements_file(source_dir, tmp_path, "test_project")

    assert result == (source_dir / "requirements.txt")


def test_find_sphinx_doc_requirements_file_not_found(tmp_path: Path, caplog) -> None:
    """Verify _find_sphinx_doc_requirements_file returns None if no file is found."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    with caplog.at_level(logging.INFO):
        result = _find_sphinx_doc_requirements_file(
            source_dir, tmp_path, "test_project"
        )

    assert result is None
    assert "No specific 'requirements.txt' found for documentation" in caplog.text


def test_build_sphinx_docs_success(mocker, tmp_path: Path) -> None:
    """Verify build_sphinx_docs successfully builds documentation."""
    mock_execute_command = mocker.patch(
        "devildex.readthedocs.readthedocs_src.execute_command", return_value=("", "", 0)
    )

    # Configure the mock IsolatedVenvManager
    mock_venv_manager_cls = mocker.patch(
        "devildex.readthedocs.readthedocs_src.IsolatedVenvManager"
    )
    mock_venv_instance = (
        mock_venv_manager_cls.return_value.__enter__.return_value
    )  # Get the instance returned by 'with' statement
    mock_venv_instance.python_executable = "/usr/bin/python"  # Set it to a string

    mocker.patch(
        "devildex.readthedocs.readthedocs_src.install_project_and_dependencies_in_venv",
        return_value=True,
    )

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "conf.py").touch()

    # Mock shutil.rmtree to prevent actual file system operations
    mocker.patch("shutil.rmtree")

    # Manually create the expected output directory for the test assertion
    expected_output_dir = tmp_path / "output" / "test_project" / "1.0"
    expected_output_dir.mkdir(parents=True, exist_ok=True)

    result = build_sphinx_docs(
        str(source_dir), "test_project", "1.0", str(tmp_path), tmp_path / "output"
    )

    assert result == str(expected_output_dir)
    mock_execute_command.assert_called_once()


def test_build_sphinx_docs_conf_py_not_found(mocker, tmp_path: Path, caplog) -> None:
    """Verify build_sphinx_docs returns None if conf.py is not found."""
    mocker.patch("devildex.readthedocs.readthedocs_src.execute_command")

    source_dir = tmp_path / "source"
    source_dir.mkdir()

    with caplog.at_level(logging.ERROR):
        result = build_sphinx_docs(
            str(source_dir), "test_project", "1.0", str(tmp_path), tmp_path / "output"
        )

    assert result is None
    assert "Critical Error: conf.py not found" in caplog.text


def test_extract_repo_url_branch_success(mocker) -> None:
    """Verify _extract_repo_url_branch extracts URL and branch correctly."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "repository": {"url": "https://github.com/user/repo"},
        "default_branch": "dev",
    }
    mocker.patch("requests.get", return_value=mock_response)

    branch, url = _extract_repo_url_branch("http://api.rtd/project", "test_project")

    assert branch == "dev"
    assert url == "https://github.com/user/repo"


def test_extract_repo_url_branch_no_repo_url(mocker, caplog) -> None:
    """Verify _extract_repo_url_branch handles missing repo URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"default_branch": "main"}
    mocker.patch("requests.get", return_value=mock_response)

    with caplog.at_level(logging.ERROR):
        branch, url = _extract_repo_url_branch("http://api.rtd/project", "test_project")

    assert branch == "main"
    assert url is None
    assert "URL del repository sources non trovato" in caplog.text


def test_extract_repo_url_branch_request_exception(mocker, caplog) -> None:
    """Verify _extract_repo_url_branch handles requests.exceptions.RequestException."""
    mocker.patch(
        "requests.get",
        side_effect=requests.exceptions.RequestException("Network error"),
    )

    with caplog.at_level(logging.ERROR):
        branch, url = _extract_repo_url_branch("http://api.rtd/project", "test_project")

    assert branch == "main"
    assert url is None
    assert "Error durante la richiesta API" in caplog.text
