"""Tests for the scanner module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from devildex.scanner.scanner import (
    has_docstrings,
    is_mkdocs_project,
    is_sphinx_project,
)


def test_is_sphinx_project_identifies_correctly(tmp_path: Path) -> None:
    """Verify that a basic Sphinx project is recognized."""
    (tmp_path / "conf.py").write_text("extensions = ['sphinx.ext.autodoc']")
    assert isinstance(is_sphinx_project(str(tmp_path)), Path)


def test_is_sphinx_project_in_docs_subdir(tmp_path: Path) -> None:
    """Verify recognition when conf.py is in a 'docs' subdirectory."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "conf.py").write_text("html_theme = 'furo'")
    assert isinstance(is_sphinx_project(str(tmp_path)), Path)


def test_is_sphinx_project_in_doc_subdir(tmp_path: Path) -> None:
    """Verify recognition when conf.py is in a 'doc' subdirectory."""
    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    (doc_dir / "conf.py").write_text("html_theme = 'furo'")
    assert isinstance(is_sphinx_project(str(tmp_path)), Path)


def test_is_sphinx_project_by_score(tmp_path: Path) -> None:
    """Verify recognition based on the score of common variables."""
    conf_content = """
project = 'My Project'
copyright = '2024, Me'
author = 'The Author'
# No other strong indicators
"""
    (tmp_path / "conf.py").write_text(conf_content)
    assert isinstance(is_sphinx_project(str(tmp_path)), Path)


def test_is_sphinx_project_with_sys_path_pattern(tmp_path: Path) -> None:
    """Verify recognition via the common sys.path modification pattern."""
    conf_content = "import os; import sys; sys.path.insert(0, os.path.abspath('.'))"
    (tmp_path / "conf.py").write_text(conf_content)
    assert isinstance(is_sphinx_project(str(tmp_path)), Path)


def test_is_sphinx_project_returns_false_for_non_sphinx(tmp_path: Path) -> None:
    """Verify that a folder without conf.py is not recognized as a Sphinx project."""
    (tmp_path / "some_file.txt").write_text("hello")
    assert is_sphinx_project(str(tmp_path)) is None


def test_is_sphinx_project_returns_false_for_irrelevant_conf(tmp_path: Path) -> None:
    """Verify that a non-relevant conf.py is not recognized as a Sphinx project."""
    (tmp_path / "conf.py").write_text("unrelated_config = True")
    assert is_sphinx_project(str(tmp_path)) is None


def test_is_sphinx_project_read_file_fails(mocker: MagicMock, tmp_path: Path) -> None:
    """Verify is_sphinx_project handles read_file_content_robustly returning None."""
    (tmp_path / "conf.py").touch()
    mocker.patch(
        "devildex.scanner.scanner.read_file_content_robustly", return_value=None
    )
    assert is_sphinx_project(str(tmp_path)) is None


def test_is_sphinx_project_score_too_low(tmp_path: Path) -> None:
    """Verify is_sphinx_project returns False if the score is below the threshold."""
    conf_content = """
project = 'My Project'
copyright = '2024, Me'
# Only 2 common variables
"""
    (tmp_path / "conf.py").write_text(conf_content)
    assert is_sphinx_project(str(tmp_path)) is None


def test_is_mkdocs_project_identifies_correctly(tmp_path: Path) -> None:
    """Verify that an MkDocs project is recognized."""
    (tmp_path / "mkdocs.yml").touch()
    assert is_mkdocs_project(tmp_path) is True


def test_is_mkdocs_project_returns_false_when_missing(tmp_path: Path) -> None:
    """Verify that a folder without mkdocs.yml is not recognized."""
    (tmp_path / "some_other_file.yml").touch()
    assert is_mkdocs_project(tmp_path) is False


def test_has_docstrings_finds_module_docstring(tmp_path: Path) -> None:
    """Verify that has_docstrings finds a module-level docstring."""
    py_file = tmp_path / "mymodule.py"
    py_file.write_text('"""This is a module docstring."""\n\nMY_VAR = 1')
    assert has_docstrings(str(tmp_path)) is True


def test_has_docstrings_finds_function_docstring(tmp_path: Path) -> None:
    """Verify detection of a docstring in a function."""
    py_file = tmp_path / "mymodule.py"
    py_file.write_text(
        'def my_func():\n    """This is a function docstring."""\n    pass'
    )
    assert has_docstrings(str(tmp_path)) is True


def test_has_docstrings_finds_class_docstring(tmp_path: Path) -> None:
    """Verify detection of a docstring in a class."""
    py_file = tmp_path / "mymodule.py"
    py_file.write_text('class MyClass:\n    """This is a class docstring."""\n    pass')
    assert has_docstrings(str(tmp_path)) is True


def test_has_docstrings_in_subdirectory(tmp_path: Path) -> None:
    """Verify detection of docstrings in a file within a subdirectory."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "submodule.py").write_text('"""Submodule docstring."""')
    assert has_docstrings(str(tmp_path)) is True


def test_has_docstrings_returns_false_for_no_docstrings(tmp_path: Path) -> None:
    """Verify that has_docstrings returns False if no docstrings are found."""
    py_file = tmp_path / "empty_module.py"
    py_file.write_text("# No docstrings here\n\nMY_VAR = 2")
    assert has_docstrings(str(tmp_path)) is False


def test_has_docstrings_handles_syntax_error_gracefully(tmp_path: Path) -> None:
    """Verify that a file with a SyntaxError does not crash the scanner."""
    (tmp_path / "broken_file.py").write_text("def my_func(:\n    pass")
    (tmp_path / "valid_file.py").write_text("a = 1")
    assert has_docstrings(str(tmp_path)) is False


def test_has_docstrings_os_error(mocker: MagicMock, tmp_path: Path) -> None:
    """Verify that an OSError during file reading is handled gracefully."""
    (tmp_path / "file.py").touch()
    mocker.patch("builtins.open", side_effect=OSError("Disk full"))
    assert has_docstrings(str(tmp_path)) is False


def test_is_sphinx_project_no_conf_file(tmp_path: Path) -> None:
    """Verify that is_sphinx_project returns False when no conf.py is found."""
    assert is_sphinx_project(str(tmp_path)) is None


def test_is_sphinx_project_read_file_content_robustly_returns_none(
    mocker: MagicMock, tmp_path: Path
) -> None:
    """Verify is_sphinx_project handles read_file_content_robustly returning None."""
    (tmp_path / "conf.py").touch()
    mocker.patch(
        "devildex.scanner.scanner.read_file_content_robustly", return_value=None
    )
    assert is_sphinx_project(str(tmp_path)) is None


def test_is_sphinx_project_irrelevant_conf_file(tmp_path: Path) -> None:
    """Verify that returns False for a conf.py with no strong Sphinx indicators."""
    conf_content = "MY_APP_NAME = 'My Custom App'\nDEBUG_MODE = True"
    (tmp_path / "conf.py").write_text(conf_content)
    assert is_sphinx_project(str(tmp_path)) is None


def test_is_mkdocs_project_explicit_call(tmp_path: Path) -> None:
    """Explicitly call is_mkdocs_project to ensure coverage."""
    (tmp_path / "mkdocs.yml").touch()
    assert is_mkdocs_project(tmp_path) is True


def test_has_docstrings_handles_syntax_error_in_file(tmp_path: Path) -> None:
    """Verify that has_docstrings handles SyntaxError in a Python file gracefully."""
    py_file = tmp_path / "broken.py"
    py_file.write_text("def func(:\n    pass")
    assert has_docstrings(str(tmp_path)) is False


def test_has_docstrings_handles_os_error_in_file(
    mocker: MagicMock, tmp_path: Path
) -> None:
    """Verify that has_docstrings handles OSError during file reading gracefully."""
    py_file = tmp_path / "unreadable.py"
    py_file.touch()
    mocker.patch("builtins.open", side_effect=OSError("Permission denied"))
    assert has_docstrings(str(tmp_path)) is False