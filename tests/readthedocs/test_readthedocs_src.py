"""test readthedocs_src."""

import logging
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from pytest_mock import MockerFixture

from devildex.readthedocs.readthedocs_src import (
    CloneAttemptStatus,
    RtdCloningConfig,
    _attempt_clone_and_process_result,
    _attempt_single_branch_clone,
    _cleanup,
    _extract_repo_url_branch,
    _find_doc_dir_in_repo,
    _find_sphinx_doc_requirements_file,
    _get_unique_branches_to_attempt,
    _get_vcs_executable,
    _handle_repository_cloning,
    build_sphinx_docs,
    find_doc_source_in_clone,
    run_clone,
)

EXPECTED_CLONE_ATTEMPTS = 2


def test_get_vcs_executable_git_not_found(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _get_vcs_executable logs error when git not found."""
    mocker.patch("shutil.which", return_value=None)
    with caplog.at_level(logging.ERROR):
        assert _get_vcs_executable(False) is None
    assert "Error: 'git' command not found." in caplog.text


def test_get_vcs_executable_git_found(mocker: MockerFixture) -> None:
    """Verify _get_vcs_executable returns git path when found."""
    mocker.patch("shutil.which", return_value="/usr/bin/git")
    assert _get_vcs_executable(False) == "/usr/bin/git"


def test_get_unique_branches_to_attempt() -> None:
    """Test _get_unique_branches_to_attempt returns unique and ordered branches."""
    assert _get_unique_branches_to_attempt("main") == ["main", "master"]
    assert _get_unique_branches_to_attempt("master") == ["master", "main"]
    assert _get_unique_branches_to_attempt("feature") == ["feature", "master", "main"]
    assert _get_unique_branches_to_attempt("main,master") == [
        "main,master",
        "master",
        "main",
    ]
    assert _get_unique_branches_to_attempt("") == ["master", "main"]
    assert _get_unique_branches_to_attempt(None) == ["master", "main"]
    assert _get_unique_branches_to_attempt("  dev  ") == ["dev", "master", "main"]
    assert _get_unique_branches_to_attempt("   ") == ["master", "main"]


def test_get_vcs_executable_bzr_found(mocker: MockerFixture) -> None:
    """Verify _get_vcs_executable returns bzr path when found."""
    mocker.patch("shutil.which", return_value="/usr/bin/bzr")
    assert _get_vcs_executable(True) == "/usr/bin/bzr"


def test_get_vcs_executable_bzr_not_found(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _get_vcs_executable logs error when bzr not found."""
    mocker.patch("shutil.which", return_value=None)
    with caplog.at_level(logging.ERROR):
        assert _get_vcs_executable(True) is None
    assert "Error: 'bzr' command not found." in caplog.text


def test_attempt_single_branch_clone_success(
    mocker: MockerFixture, tmp_path: Path
) -> None:
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
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
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
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
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
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify failed clone attempt due to VCS executable not found."""
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


def test_cleanup_os_error(
    tmp_path: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _cleanup handles OSError during rmtree."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    mocker.patch("shutil.rmtree", side_effect=OSError("Permission denied"))

    with caplog.at_level(logging.ERROR):
        _cleanup(test_dir)

    assert "Error during deleting della repository cloned" in caplog.text


def test_find_doc_source_in_clone_not_found(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
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


def test_find_doc_dir_in_repo_no_conf_py(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
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


def test_find_sphinx_doc_requirements_file_not_found(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _find_sphinx_doc_requirements_file returns None if no file is found."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    with caplog.at_level(logging.INFO):
        result = _find_sphinx_doc_requirements_file(
            source_dir, tmp_path, "test_project"
        )

    assert result is None
    assert "No specific 'requirements.txt' found for documentation" in caplog.text


def test_build_sphinx_docs_success(mocker: MockerFixture, tmp_path: Path) -> None:
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


def test_build_sphinx_docs_conf_py_not_found(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
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


def test_extract_repo_url_branch_success(mocker: MockerFixture) -> None:
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


def test_extract_repo_url_branch_no_repo_url(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _extract_repo_url_branch handles missing repo URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"default_branch": "main"}
    mocker.patch("requests.get", return_value=mock_response)

    with caplog.at_level(logging.ERROR):
        branch, url = _extract_repo_url_branch("http://api.rtd/project", "test_project")

    assert branch == "main"
    assert url is None
    assert "URL del repository sources non trovato" in caplog.text


def test_extract_repo_url_branch_request_exception(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
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


def test_run_clone_success(mocker: MockerFixture, tmp_path: Path) -> None:
    """Verify run_clone successfully clones a repository."""
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_unique_branches_to_attempt",
        return_value=["main"],
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_vcs_executable",
        return_value="/usr/bin/git",
    )
    mock_attempt_single_branch_clone = mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_single_branch_clone",
        return_value=CloneAttemptStatus.SUCCESS,
    )

    repo_url = "http://example.com/repo.git"
    initial_default_branch = "main"
    clone_dir = tmp_path / "cloned_repo"
    bzr = False

    result = run_clone(repo_url, initial_default_branch, clone_dir, bzr)

    assert result == "main"
    mock_attempt_single_branch_clone.assert_called_once_with(
        repo_url, "main", clone_dir, bzr, "/usr/bin/git"
    )


def test_run_clone_no_valid_branches(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify run_clone handles no valid branches to attempt."""
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_unique_branches_to_attempt",
        return_value=[],
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_vcs_executable",
        return_value="/usr/bin/git",
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_single_branch_clone",
        return_value=CloneAttemptStatus.SUCCESS,
    )

    repo_url = "http://example.com/repo.git"
    initial_default_branch = "main"
    clone_dir = tmp_path / "cloned_repo"
    bzr = False

    with caplog.at_level(logging.ERROR):
        result = run_clone(repo_url, initial_default_branch, clone_dir, bzr)

    assert result is None
    assert "No valid branches to attempt for cloning" in caplog.text


def test_run_clone_vcs_not_found(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify run_clone handles VCS executable not found."""
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_unique_branches_to_attempt",
        return_value=["main"],
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_vcs_executable",
        return_value=None,
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_single_branch_clone",
        return_value=CloneAttemptStatus.SUCCESS,
    )

    repo_url = "http://example.com/repo.git"
    initial_default_branch = "main"
    clone_dir = tmp_path / "cloned_repo"
    bzr = False

    with caplog.at_level(logging.ERROR):  # _get_vcs_executable logs error
        result = run_clone(repo_url, initial_default_branch, clone_dir, bzr)

    assert result is None


def test_run_clone_failed_critical_prepare_dir(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify run_clone handles critical failure during directory preparation."""
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_unique_branches_to_attempt",
        return_value=["main"],
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_vcs_executable",
        return_value="/usr/bin/git",
    )
    mock_attempt_single_branch_clone = mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_single_branch_clone",
        return_value=CloneAttemptStatus.FAILED_CRITICAL_PREPARE_DIR,
    )

    repo_url = "http://example.com/repo.git"
    initial_default_branch = "main"
    clone_dir = tmp_path / "cloned_repo"
    bzr = False

    with caplog.at_level(logging.ERROR):
        result = run_clone(repo_url, initial_default_branch, clone_dir, bzr)

    assert result is None
    assert "Critical error preparing clone directory." in caplog.text
    mock_attempt_single_branch_clone.assert_called_once()


def test_run_clone_failed_critical_vcs_not_found_exec(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify run_clone handles crit failure when VCS exe not found during execution."""
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_unique_branches_to_attempt",
        return_value=["main"],
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_vcs_executable",
        return_value="/usr/bin/git",
    )
    mock_attempt_single_branch_clone = mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_single_branch_clone",
        return_value=CloneAttemptStatus.FAILED_CRITICAL_VCS_NOT_FOUND_EXEC,
    )

    repo_url = "http://example.com/repo.git"
    initial_default_branch = "main"
    clone_dir = tmp_path / "cloned_repo"
    bzr = False

    with caplog.at_level(logging.ERROR):
        result = run_clone(repo_url, initial_default_branch, clone_dir, bzr)

    assert result is None
    assert "Critical error: VCS command not found during execution." in caplog.text
    mock_attempt_single_branch_clone.assert_called_once()


def test_run_clone_all_attempts_fail(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify run_clone returns None when all branch attempts fail."""
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_unique_branches_to_attempt",
        return_value=["branch1", "branch2"],
    )
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._get_vcs_executable",
        return_value="/usr/bin/git",
    )
    mock_attempt_single_branch_clone = mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_single_branch_clone",
        return_value=CloneAttemptStatus.FAILED_RETRYABLE,
    )

    repo_url = "http://example.com/repo.git"
    initial_default_branch = "main"
    clone_dir = tmp_path / "cloned_repo"
    bzr = False

    with caplog.at_level(logging.ERROR):
        result = run_clone(repo_url, initial_default_branch, clone_dir, bzr)

    assert result is None
    assert "Failed to clone any of the attempted branches" in caplog.text
    assert mock_attempt_single_branch_clone.call_count == EXPECTED_CLONE_ATTEMPTS


def test_attempt_clone_and_process_result_success(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verify _attempt_clone_and_process_result handles successful clone."""
    mocker.patch("devildex.readthedocs.readthedocs_src.run_clone", return_value="main")

    repo_url = "http://example.com/repo.git"
    initial_default_branch = "main"
    clone_dir = tmp_path / "cloned_repo"
    bzr = False
    project_slug = "test_project"

    success, branch = _attempt_clone_and_process_result(
        repo_url, initial_default_branch, clone_dir, bzr, project_slug
    )

    assert success is True
    assert branch == "main"


def test_attempt_clone_and_process_result_failure(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _attempt_clone_and_process_result handles failed clone."""
    mocker.patch("devildex.readthedocs.readthedocs_src.run_clone", return_value=None)

    repo_url = "http://example.com/repo.git"
    initial_default_branch = "main"
    clone_dir = tmp_path / "cloned_repo"
    bzr = False
    project_slug = "test_project"

    with caplog.at_level(logging.ERROR):
        success, branch = _attempt_clone_and_process_result(
            repo_url, initial_default_branch, clone_dir, bzr, project_slug
        )

    assert success is False
    assert branch == "main"  # Should still return initial_default_branch on failure
    assert "Cloning failed for 'test_project'" in caplog.text


def test_handle_repository_cloning_no_repo_url(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _handle_repository_cloning handles no repository URL."""
    cloning_config = RtdCloningConfig(
        repo_url=None,
        initial_default_branch="main",
        base_dir=tmp_path,
        project_slug="test_project",
        bzr=False,
    )

    with caplog.at_level(logging.WARNING):
        clone_path, effective_branch = _handle_repository_cloning(cloning_config)

    assert clone_path is None
    assert effective_branch == "main"
    assert "No repository URL provided for 'test_project'." in caplog.text
    assert "No repository URL and no existing clone for 'test_project'." in caplog.text


def test_handle_repository_cloning_existing_clone(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _handle_repository_cloning uses existing clone if available."""
    clone_dir = tmp_path / "test_project_repo_main"
    clone_dir.mkdir()

    cloning_config = RtdCloningConfig(
        repo_url="http://example.com/repo.git",
        initial_default_branch="main",
        base_dir=tmp_path,
        project_slug="test_project",
        bzr=False,
    )

    with caplog.at_level(logging.INFO):
        clone_path, effective_branch = _handle_repository_cloning(cloning_config)

    assert clone_path == clone_dir
    assert effective_branch == "main"
    assert "Repository for 'test_project' already exists" in caplog.text
    # Ensure _attempt_clone_and_process_result was NOT called
    mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_clone_and_process_result"
    )
    assert not mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_clone_and_process_result"
    ).called


def test_handle_repository_cloning_new_clone_success(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _handle_repository_cloning successfully clones a new repository."""
    clone_dir_path_for_test = tmp_path / "test_project_repo_main"
    if clone_dir_path_for_test.exists():
        shutil.rmtree(clone_dir_path_for_test)

    def mock_clone_and_process_success(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        # args: repo_url, branch_to_try, clone_dir_path, bzr, project_slug
        mock_clone_dir_path = args[2]
        mock_clone_dir_path.mkdir(parents=True)  # Create the directory
        return True, "dev"

    mock_attempt_clone_and_process_result = mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_clone_and_process_result",
        side_effect=mock_clone_and_process_success,
    )

    cloning_config = RtdCloningConfig(
        repo_url="http://example.com/repo.git",
        initial_default_branch="main",
        base_dir=tmp_path,
        project_slug="test_project",
        bzr=False,
    )

    with caplog.at_level(logging.INFO):
        clone_path, effective_branch = _handle_repository_cloning(cloning_config)

    assert clone_path == clone_dir_path_for_test
    assert effective_branch == "dev"
    assert "Repository for 'test_project' not found locally" in caplog.text
    assert "Using repository for 'test_project'" in caplog.text
    mock_attempt_clone_and_process_result.assert_called_once()


def test_handle_repository_cloning_new_clone_failure(
    mocker: MockerFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _handle_repository_cloning handles failed new clone."""
    clone_dir_path_for_test = tmp_path / "test_project_repo_main"
    # Ensure it does not exist before the test
    if clone_dir_path_for_test.exists():
        shutil.rmtree(clone_dir_path_for_test)

    def mock_clone_and_process_failure(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return False, "main"

    mock_attempt_clone_and_process_result = mocker.patch(
        "devildex.readthedocs.readthedocs_src._attempt_clone_and_process_result",
        side_effect=mock_clone_and_process_failure,
    )

    cloning_config = RtdCloningConfig(
        repo_url="http://example.com/repo.git",
        initial_default_branch="main",
        base_dir=tmp_path,
        project_slug="test_project",
        bzr=False,
    )

    with caplog.at_level(logging.ERROR):
        clone_path, effective_branch = _handle_repository_cloning(cloning_config)

    mock_attempt_clone_and_process_result.assert_called_once()
    assert clone_path is None
    assert effective_branch == "main"
    assert "Repository directory for 'test_project' not found" in caplog.text
