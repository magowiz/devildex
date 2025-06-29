"""test docstrings."""

import logging
from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from devildex.docstrings.docstrings_src import DocStringsSrc

logger = logging.getLogger(__name__)
PACKAGES_TO_TEST = [
    {
        "repo_url": "https://github.com/psf/black.git",
        "project_name": "black",
        "version_tag": "24.4.2",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/pallets/flask.git",
        "project_name": "flask",
        "version_tag": "3.0.3",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/Textualize/rich.git",
        "project_name": "rich",
        "version_tag": "13.7.1",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/tiangolo/fastapi.git",
        "project_name": "fastapi",
        "version_tag": "0.111.0",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/requests/requests.git",
        "project_name": "requests",
        "version_tag": "v2.32.3",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/pallets/click.git",
        "project_name": "click",
        "version_tag": "8.1.7",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/benjaminp/six.git",
        "project_name": "six",
        "version_tag": "1.16.0",
        "expected_entry_point": "index.html",
    },
]

doc_params = [
    pytest.param(package_info, id=package_info["project_name"])
    for package_info in PACKAGES_TO_TEST
]


@pytest.fixture
def manage_test_output_directory(
    tmp_path: Path,
) -> Path:
    """Fixture for Create and provide an output documentation directory.

    within the temporary space of a specific test.
    """
    test_specific_doc_output_dir = tmp_path / "doc_gen_output"
    test_specific_doc_output_dir.mkdir(parents=True, exist_ok=True)

    return test_specific_doc_output_dir


@pytest.mark.parametrize("package_info", doc_params)
def test_documentation_generation_for_package(
    package_info: dict[str, Any],
    tmp_path: Path,
    manage_test_output_directory: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test documentation generation for a package."""
    repo_url = package_info["repo_url"]
    project_name = package_info["project_name"]
    version_tag = package_info.get("version_tag")
    expected_entry_point = package_info.get("expected_entry_point")

    clone_cwd = tmp_path / "clone_area"
    clone_cwd.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(clone_cwd)

    current_test_docs_output_base = manage_test_output_directory
    logger.info(f"[Testing] package:{project_name}, Version:{version_tag or 'default'}")

    logger.info(
        "Output Base Docs (isolato per questo test): "
        f"{current_test_docs_output_base.resolve()}"
    )
    logger.info(f"Current Working Directory (per il clone): {Path.cwd().resolve()}")

    doc_generator = DocStringsSrc(output_dir=str(current_test_docs_output_base))
    try:
        doc_generator.run(url=repo_url, project_name=project_name)
    except Exception as e:
        pytest.fail(
            f"The execution of doc_generator.run per{project_name} has failed "
            f"with an exception:{e} Check the previous logs for details."
        )

    final_project_version_docs_dir = current_test_docs_output_base / project_name

    assert final_project_version_docs_dir.exists(), (
        "The final directory of the versioned documentation does not exist:"
        f"{final_project_version_docs_dir}"
    )

    assert final_project_version_docs_dir.is_dir(), (
        "The Path of the versioned documentation is not a directory: "
        f"{final_project_version_docs_dir}"
    )

    html_files = list(final_project_version_docs_dir.rglob("*.html"))
    assert (
        len(html_files) > 0
    ), f"No file HTML trovato in: {final_project_version_docs_dir}"
    logger.info(
        f"Found {len(html_files)} file HTML in {final_project_version_docs_dir}."
    )

    if expected_entry_point:
        entry_point_file = final_project_version_docs_dir / expected_entry_point
        assert (
            entry_point_file.exists()
        ), f"The expected entry point file was not found:{entry_point_file}"
        assert (
            entry_point_file.is_file()
        ), f"The expected HTML entry point Path is not a file:{entry_point_file}"
        logger.error(f"Found entry point html expected:{entry_point_file}")
