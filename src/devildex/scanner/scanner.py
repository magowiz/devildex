import re
import shutil
from pathlib import Path

from src.devildex.scanner_utils.scanner_utils import (
    check_content_patterns,
    count_matching_strings,
    find_config_files,
    read_file_content_robustly,
)


def is_sphinx_project(project_path: str) -> bool:
    """
    Scan project path to determine if it is a Sphinx project.

    Args:
        project_path: root directory path of project to scan.

    Returns:
        True if il project is identified as Sphinx, False otherwise.
    """
    project_dir = Path(project_path)

    potential_conf_dirs = [project_dir, project_dir / "docs", project_dir / "doc"]

    conf_file_paths = find_config_files(potential_conf_dirs, "conf.py")

    if not conf_file_paths:
        print(f"  ❌ No 'conf.py' file found in standard positions for {project_path}")
        return False

    print(f"  🔍 Found {len(conf_file_paths)} file 'conf.py'. Analyzing content...")

    for conf_file_path in conf_file_paths:
        print(f"    Analyzing: {conf_file_path}")

        content = read_file_content_robustly(conf_file_path)
        if content is None:
            continue

        high_priority_sphinx_checks = [
            (
                r"extensions\s*=\s*\[.*?['\"]sphinx\.ext\."
                r"(autodoc|napoleon|intersphinx|viewcode|todo|coverage)['\"].*?\]",
                "Found extension 'sphinx.ext.*' key in 'extensions'. Very probably Sphinx.",
            ),
            (
                r"html_theme\s*=\s*['\"](alabaster|sphinx_rtd_theme|furo|pydata_sphinx_theme)['\"]",
                "Trovato 'html_theme' con known theme Sphinx. Very probably Sphinx.",
            ),
            (
                r"https://www\.sphinx-doc\.org/en/master/usage/configuration\.html",
                "Trovato link alla official documentation Sphinx. Probably Sphinx.",
            ),
            (
                r"import os\s*;\s*import sys\s*;\s*sys\.path\.insert\(0,\s*os\.path\.abspath\(",
                "Trovato setup comune del sys.path per autodoc. Forte indication.",
            ),
        ]

        success_message = check_content_patterns(
            content, high_priority_sphinx_checks, re.DOTALL | re.MULTILINE
        )
        if success_message:
            print(f"    ✅ {success_message}")
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

        if score >= 3:
            print(
                f"    ✅ Found {score} common configuration Sphinx variables. Good indication."
            )
            return True

    print(
        f"  ❌ No criteria Sphinx forte trovato nel file 'conf.py' per {project_path}."
    )
    return False


if __name__ == "__main__":
    test_sphinx_dir = Path("./SPHINX_DOCS_EXAMPLE")
    test_sphinx_dir.mkdir(exist_ok=True)
    (test_sphinx_dir / "conf.py").write_text(
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

    print(f"\nScanning {test_sphinx_dir.name}/:")
    if is_sphinx_project(str(test_sphinx_dir)):
        print(f"Result finale: {test_sphinx_dir.name} è un project Sphinx.")
    else:
        print(f"Result finale: {test_sphinx_dir.name} NON è un project Sphinx.")

    print(f"\nScanning {test_sphinx_dir_docs.name}/:")
    if is_sphinx_project(str(test_sphinx_dir_docs)):
        print(f"Result finale: {test_sphinx_dir_docs.name} è un project Sphinx.")
    else:
        print(f"final Result: {test_sphinx_dir_docs.name} is NOT a Sphinx project.")

    print("\n--- Test su una directory che NON è Sphinx (simulation) ---")

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

    print(f"\nScanning {test_non_sphinx_dir.name}/:")
    if is_sphinx_project(str(test_non_sphinx_dir)):
        print(f"final Result: {test_non_sphinx_dir.name} è un project Sphinx.")
    else:
        print(f"final Result: {test_non_sphinx_dir.name} NON è un project Sphinx.")

    print(f"\nScanning {test_non_sphinx_dir_no_conf.name}/:")
    if is_sphinx_project(str(test_non_sphinx_dir_no_conf)):
        print(f"final Result: {test_non_sphinx_dir_no_conf.name} è un project Sphinx.")
    else:
        print(
            f"final Result: {test_non_sphinx_dir_no_conf.name} NON è un project Sphinx."
        )

    print("\nCleaning directory di test...")
    shutil.rmtree(test_sphinx_dir, ignore_errors=True)
    shutil.rmtree(test_sphinx_dir_docs, ignore_errors=True)
    shutil.rmtree(test_non_sphinx_dir, ignore_errors=True)
    shutil.rmtree(test_non_sphinx_dir_no_conf, ignore_errors=True)
    print("Done.")
