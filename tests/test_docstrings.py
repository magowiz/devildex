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


@pytest.fixture
def manage_test_output_directory(
    tmp_path: Path,
) -> Path:
    """Fixture per create e fornire una directory di output documentation.

    all'interno dello spazio temporaneo di un test specifico.
    """
    test_specific_doc_output_dir = tmp_path / "doc_gen_output"
    test_specific_doc_output_dir.mkdir(parents=True, exist_ok=True)

    return test_specific_doc_output_dir


@pytest.mark.parametrize("package_info", PACKAGES_TO_TEST)
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
    logger.info(
        f"\n[Testing] Pacchetto: {project_name}, Versione: {version_tag or 'default'}"
    )
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
            f"L'esecuzione di doc_generator.run per {project_name} ha failed con "
            f"un'eccezione: {e}\n"
            f"Controlla i log precedenti per dettagli."
        )

    final_project_version_docs_dir = current_test_docs_output_base / project_name

    assert final_project_version_docs_dir.exists(), (
        "La directory finale della documentazione versionata non esiste: "
        f"{final_project_version_docs_dir}"
    )
    assert final_project_version_docs_dir.is_dir(), (
        "Il path della documentazione versionata non è una directory: "
        f"{final_project_version_docs_dir}"
    )

    html_files = list(final_project_version_docs_dir.rglob("*.html"))
    assert (
        len(html_files) > 0
    ), f"No file HTML trovato in: {final_project_version_docs_dir}"
    logger.info(
        f"Found {len(html_files)} file HTML in " f"{final_project_version_docs_dir}."
    )

    if expected_entry_point:
        entry_point_file = final_project_version_docs_dir / expected_entry_point
        assert (
            entry_point_file.exists()
        ), f"Il file di entry point HTML atteso non è stato trovato: {entry_point_file}"
        assert (
            entry_point_file.is_file()
        ), f"Il path dell'entry point HTML atteso non è un file: {entry_point_file}"
        logger.error(f"Trovato entry point HTML atteso: {entry_point_file}")
