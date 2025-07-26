"""Tests for the scanner module."""

from pathlib import Path

from devildex.scanner.scanner import (
    has_docstrings,
    is_mkdocs_project,
    is_sphinx_project,
)

# --- Tests for is_sphinx_project ---


def test_is_sphinx_project_identifies_correctly(tmp_path: Path) -> None:
    """Verify that a basic Sphinx project is recognized."""
    # Arrange: Create a mock Sphinx project structure
    (tmp_path / "conf.py").write_text("extensions = ['sphinx.ext.autodoc']")

    # Act & Assert
    assert is_sphinx_project(str(tmp_path)) is True


def test_is_sphinx_project_in_docs_subdir(tmp_path: Path) -> None:
    """Verify recognition when conf.py is in a 'docs' subdirectory."""
    # Arrange
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "conf.py").write_text("html_theme = 'furo'")

    # Act & Assert
    assert is_sphinx_project(str(tmp_path)) is True


def test_is_sphinx_project_in_doc_subdir(tmp_path: Path) -> None:
    """Verify recognition when conf.py is in a 'doc' subdirectory."""
    # Arrange
    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    (doc_dir / "conf.py").write_text("html_theme = 'furo'")

    # Act & Assert
    assert is_sphinx_project(str(tmp_path)) is True


def test_is_sphinx_project_by_score(tmp_path: Path) -> None:
    """Verify recognition based on the score of common variables."""
    # Arrange
    conf_content = """
project = 'My Project'
copyright = '2024, Me'
author = 'The Author'
# No other strong indicators
"""
    (tmp_path / "conf.py").write_text(conf_content)

    # Act & Assert
    assert is_sphinx_project(str(tmp_path)) is True


def test_is_sphinx_project_with_sys_path_pattern(tmp_path: Path) -> None:
    """Verify recognition via the common sys.path modification pattern."""
    # Arrange
    conf_content = "import os; import sys; sys.path.insert(0, os.path.abspath('.'))"
    (tmp_path / "conf.py").write_text(conf_content)

    # Act & Assert
    assert is_sphinx_project(str(tmp_path)) is True


def test_is_sphinx_project_returns_false_for_non_sphinx(tmp_path: Path) -> None:
    """Verify that a folder without conf.py is not recognized as a Sphinx project."""
    # Arrange
    (tmp_path / "some_file.txt").write_text("hello")

    # Act & Assert
    assert is_sphinx_project(str(tmp_path)) is False


def test_is_sphinx_project_returns_false_for_irrelevant_conf(tmp_path: Path) -> None:
    """Verify that a non-relevant conf.py is not recognized as a Sphinx project."""
    # Arrange
    (tmp_path / "conf.py").write_text("unrelated_config = True")

    # Act & Assert
    assert is_sphinx_project(str(tmp_path)) is False


# --- Tests for is_mkdocs_project ---


def test_is_mkdocs_project_identifies_correctly(tmp_path: Path) -> None:
    """Verify that an MkDocs project is recognized."""
    # Arrange
    (tmp_path / "mkdocs.yml").touch()

    # Act & Assert
    assert is_mkdocs_project(tmp_path) is True


def test_is_mkdocs_project_returns_false_when_missing(tmp_path: Path) -> None:
    """Verify that a folder without mkdocs.yml is not recognized."""
    # Arrange
    (tmp_path / "some_other_file.yml").touch()

    # Act & Assert
    assert is_mkdocs_project(tmp_path) is False


# --- Tests for has_docstrings ---


def test_has_docstrings_finds_module_docstring(tmp_path: Path) -> None:
    """Verify that has_docstrings finds a module-level docstring."""
    # Arrange
    py_file = tmp_path / "mymodule.py"
    py_file.write_text('"""This is a module docstring."""\n\nMY_VAR = 1')

    # Act & Assert
    assert has_docstrings(str(tmp_path)) is True


def test_has_docstrings_finds_function_docstring(tmp_path: Path) -> None:
    """Verify detection of a docstring in a function."""
    # Arrange
    py_file = tmp_path / "mymodule.py"
    py_file.write_text(
        'def my_func():\n    """This is a function docstring."""\n    pass'
    )

    # Act & Assert
    assert has_docstrings(str(tmp_path)) is True


def test_has_docstrings_finds_class_docstring(tmp_path: Path) -> None:
    """Verify detection of a docstring in a class."""
    # Arrange
    py_file = tmp_path / "mymodule.py"
    py_file.write_text('class MyClass:\n    """This is a class docstring."""\n    pass')

    # Act & Assert
    assert has_docstrings(str(tmp_path)) is True


def test_has_docstrings_in_subdirectory(tmp_path: Path) -> None:
    """Verify detection of docstrings in a file within a subdirectory."""
    # Arrange
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "submodule.py").write_text('"""Submodule docstring."""')

    # Act & Assert
    assert has_docstrings(str(tmp_path)) is True


def test_has_docstrings_returns_false_for_no_docstrings(tmp_path: Path) -> None:
    """Verify that has_docstrings returns False if no docstrings are found."""
    # Arrange
    py_file = tmp_path / "empty_module.py"
    py_file.write_text("# No docstrings here\n\nMY_VAR = 2")

    # Act & Assert
    assert has_docstrings(str(tmp_path)) is False


def test_has_docstrings_handles_syntax_error_gracefully(tmp_path: Path) -> None:
    """Verify that a file with a SyntaxError does not crash the scanner."""
    # Arrange: Create a file with a syntax error
    (tmp_path / "broken_file.py").write_text("def my_func(:\n    pass")
    # Arrange: Create another valid file without a docstring to ensure the result is False
    (tmp_path / "valid_file.py").write_text("a = 1")

    # Act & Assert: The scanner should not raise an exception and should
    # return False because it finds no docstrings in any valid files.
    assert has_docstrings(str(tmp_path)) is False
