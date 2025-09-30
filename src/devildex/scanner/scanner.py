"""scanner module."""

import ast
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from devildex.constants import CONF_FILENAME
from devildex.scanner_utils.scanner_utils import (
    check_content_patterns,
    count_matching_strings,
    find_config_files,
    read_file_content_robustly,
)

logger = logging.getLogger(__name__)
SCORE_MAX = 3
MKDOCS_CONFIG_FILE = "mkdocs.yml"


def is_sphinx_project(project_path: str) -> bool:
    """Scan project path to determine if it is a Sphinx project.

    Args:
        project_path: root directory path of project to scan.

    Returns:
        True if il project is identified as Sphinx, False otherwise.

    """
    project_dir = Path(project_path)

    potential_conf_dirs = [project_dir, project_dir / "docs", project_dir / "doc"]

    conf_file_paths = find_config_files(potential_conf_dirs, CONF_FILENAME)

    if not conf_file_paths:
        logger.error(
            "  ❌ No 'conf.py' file found in standard positions for" f" {project_path}"
        )
        return False

    logger.info(
        f"  🔍 Found {len(conf_file_paths)} file 'conf.py'. " "Analyzing content..."
    )

    for conf_file_path in conf_file_paths:
        logger.info(f"    Analyzing: {conf_file_path}")

        content = read_file_content_robustly(conf_file_path)
        if content is None:
            continue

        high_priority_sphinx_checks = [
            (
                r"extensions\s*=\s*\[.*?['\"]sphinx\.ext\."
                r"(autodoc|napoleon|intersphinx|viewcode|todo|coverage)['\"].*?\]",
                "Found extension 'sphinx.ext.*' key in 'extensions'. "
                "Very probably Sphinx.",
            ),
            (
                r"html_theme\s*=\s*['\"]"
                r"(alabaster|sphinx_rtd_theme|furo|pydata_sphinx_theme)['\"]",
                "Trovato 'html_theme' con known theme Sphinx. Very probably Sphinx.",
            ),
            (
                r"https://www\.sphinx-doc\.org/en/master/usage/configuration\.html",
                "Trovato link alla official documentation Sphinx. Probably Sphinx.",
            ),
            (
                r"import os\s*;\s*import sys\s*;\s*sys\.path\.insert"
                r"\(0,\s*os\.path\.abspath\(",
                "Trovato setup comune del sys.path per autodoc. Forte indication.",
            ),
        ]

        success_message = check_content_patterns(
            content, high_priority_sphinx_checks, re.DOTALL | re.MULTILINE
        )
        if success_message:
            logger.info(f"    ✅ {success_message}")
            return True

        common_sphinx_vars = [
            "project =",
            "copyright =",
            "author =",
            "source_suffix =",
            "master_doc =",
            "version =",
            "release =",
            "templates_path =",
            "exclude_patterns =",
        ]

        score = count_matching_strings(content, common_sphinx_vars)

        if score >= SCORE_MAX:
            logger.info(
                f"    ✅ Found {score} common configuration Sphinx variables."
                " Good indication."
            )
            return True

    logger.error(
        f"  ❌ No criteria Sphinx forte trovato nel file 'conf.py' per {project_path}."
    )
    return False


def is_mkdocs_project(project_root_path: str | Path) -> bool:
    """Check if the given path is likely an MkDocs project by looking for mkdocs.yml."""
    root_path = Path(project_root_path)
    mkdocs_conf_path = root_path / MKDOCS_CONFIG_FILE
    if mkdocs_conf_path.is_file():
        logger.info(f"Found MkDocs config file: {mkdocs_conf_path}")
        return True
    logger.debug(f"MkDocs config file not found at {mkdocs_conf_path}")
    return False


if __name__ == "__main__":
    test_sphinx_dir = Path("./SPHINX_DOCS_EXAMPLE")
    test_sphinx_dir.mkdir(exist_ok=True)
    (test_sphinx_dir / CONF_FILENAME).write_text(
        """
# conf.py
# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys
sys.path.insert(0, os.path.abspath('.'))
project = 'My Test Project'
copyright = '2024, Me'
author = 'Me'
version = '0.1'
release = '0.1.0'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]
html_theme = 'sphinx_rtd_theme'
source_suffix = '.rst'
master_doc = 'index'
"""
    )

    test_sphinx_dir_docs = Path("./SPHINX_PROJ_EXAMPLE")
    test_sphinx_dir_docs.mkdir(exist_ok=True)
    (test_sphinx_dir_docs / "docs").mkdir(exist_ok=True)
    (test_sphinx_dir_docs / "docs" / "conf.py").write_text(
        """
# conf.py per un projecto con docs/
project = 'Another Test Project'
copyright = '2024, Tester'
author = 'Tester'
extensions = [
    'sphinx.ext.todo',
    'sphinx.ext.intersphinx',
]
html_theme = 'alabaster'
"""
    )
    (test_sphinx_dir_docs / "src").mkdir(exist_ok=True)

    logger.info(f"\nScanning {test_sphinx_dir.name}/:")
    if is_sphinx_project(str(test_sphinx_dir)):
        logger.info(f"Result finale: {test_sphinx_dir.name} è un project Sphinx.")
    else:
        logger.error(f"Result finale: {test_sphinx_dir.name} NON è un project Sphinx.")

    logger.info(f"\nScanning {test_sphinx_dir_docs.name}/:")
    if is_sphinx_project(str(test_sphinx_dir_docs)):
        logger.info(f"Result finale: {test_sphinx_dir_docs.name} è un project Sphinx.")
    else:
        logger.error(
            f"final Result: {test_sphinx_dir_docs.name} " "is NOT a Sphinx project."
        )

    logger.info("\n--- Test su una directory che NON è Sphinx (simulation) ---")

    test_non_sphinx_dir = Path("./NOT_SPHINX_EXAMPLE")
    test_non_sphinx_dir.mkdir(exist_ok=True)
    (test_non_sphinx_dir / "conf.py").write_text(
        """
# Questa è una configuration for another thing
MY_APP_NAME = "My Custom App"
DEBUG_MODE = True
LOG_LEVEL = "INFO"
"""
    )

    test_non_sphinx_dir_no_conf = Path("./WITHOUT_CONF_EXAMPLE")
    test_non_sphinx_dir_no_conf.mkdir(exist_ok=True)

    logger.info(f"\nScanning {test_non_sphinx_dir.name}/:")
    if is_sphinx_project(str(test_non_sphinx_dir)):
        logger.info(f"final Result: {test_non_sphinx_dir.name} è un project Sphinx.")
    else:
        logger.error(
            f"final Result: {test_non_sphinx_dir.name} " "NON è un project Sphinx."
        )

    logger.info(f"\nScanning {test_non_sphinx_dir_no_conf.name}/:")
    if is_sphinx_project(str(test_non_sphinx_dir_no_conf)):
        logger.info(
            f"final Result: {test_non_sphinx_dir_no_conf.name} " "è un project Sphinx."
        )
    else:
        logger.error(
            f"final Result: {test_non_sphinx_dir_no_conf.name} NON è un project Sphinx."
        )

    logger.info("\nCleaning directory di test...")
    shutil.rmtree(test_sphinx_dir, ignore_errors=True)
    shutil.rmtree(test_sphinx_dir_docs, ignore_errors=True)
    shutil.rmtree(test_non_sphinx_dir, ignore_errors=True)
    shutil.rmtree(test_non_sphinx_dir_no_conf, ignore_errors=True)
    logger.info("Done.")


def _check_file_for_docstrings(file_path: Path) -> bool:
    """Check a single Python file for module, function, or class docstrings.

    Returns True if any docstring is found, False otherwise.
    """
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            source_code = f.read()
        tree = ast.parse(source_code, filename=str(file_path))
        if ast.get_docstring(tree):
            return True
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ) and ast.get_docstring(node):
                return True
    except SyntaxError:
        logging.exception("syntax error exception")
    except (OSError, ValueError):
        logging.exception("generic exception")
    return False


def has_docstrings(project_path: str) -> bool:
    """Detect if a project has docstrings in its Python source files."""
    project_dir = Path(project_path)

    for root, _, files in os.walk(project_dir):
        for file_name in files:
            if file_name.endswith(".py"):
                file_path = Path(root) / file_name
                if _check_file_for_docstrings(file_path):
                    return True
    return False


def _find_python_package_root(scan_base_path: Path) -> Optional[Path]:
    """Attempt to find the root of the main Python package within a given base path.

    This is crucial for tools like pdoc or pydoctor that need to be pointed
    at an importable package or module.
    """
    logger.debug("Searching for Python package root in: %s", scan_base_path)

    # Strategy 1: Look for a direct subdirectory with __init__.py
    for item in scan_base_path.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            logger.debug(
                "Found Python package root directly under project root: %s", item
            )
            return item

    # Strategy 2: Look for a 'src' directory containing a package
    src_dir = scan_base_path / "src"
    if src_dir.is_dir():
        for item in src_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                logger.debug("Found Python package root in src/: %s", item)
                return item

    # Strategy 3: Check if the base path itself is a package (contains __init__.py)
    if (scan_base_path / "__init__.py").exists():
        logger.debug("Project root itself is a Python package: %s", scan_base_path)
        return scan_base_path

    if (scan_base_path / "setup.py").is_file() or (
        scan_base_path / "pyproject.toml"
    ).is_file():
        logger.debug(
            "Found setup.py or pyproject.toml, assuming project root "
            "is package root: %s",
            scan_base_path,
        )
        return scan_base_path

    if any(f.suffix == ".py" for f in scan_base_path.iterdir() if f.is_file()):
        logger.debug(
            "No specific package/setup file found, "
            "using base path as implicit module root: %s",
            scan_base_path,
        )
        return scan_base_path

    logger.warning("Could not find a clear Python package root in %s", scan_base_path)
    return None
