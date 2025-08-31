import logging

from devildex.readthedocs.readthedocs_src import (
    _get_unique_branches_to_attempt,
    _get_vcs_executable,
)


def test_get_vcs_executable_git_not_found(mocker, caplog) -> None:
    """Verify _get_vcs_executable logs error when git not found."""
    mocker.patch("shutil.which", return_value=None)
    with caplog.at_level(logging.ERROR):
        assert _get_vcs_executable(False) is None
    assert "Error: 'git' command not found." in caplog.text


def test_get_vcs_executable_git_found(mocker) -> None:
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
