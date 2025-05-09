"""test docstrings."""
import shutil
from pathlib import Path

import pytest

from devildex.docstrings.docstrings_src import DocStringsSrc

PACKAGES_TO_TEST = [
    {
        "repo_url": "https://github.com/psf/black.git",
        "project_name": "black",
        "version_tag": "24.4.2",
        "expected_entry_point": "black/index.html",
    },
    {
        "repo_url": "https://github.com/pallets/flask.git",
        "project_name": "flask",
        "version_tag": "3.0.3",
        "expected_entry_point": "flask/index.html",
    },
    {
        "repo_url": "https://github.com/pytest-dev/pytest.git",
        "project_name": "pytest",
        "version_tag": "8.2.2",
        "expected_entry_point": "pytest/index.html",
    },
    {
        "repo_url": "https://github.com/Textualize/rich.git",
        "project_name": "rich",
        "version_tag": "13.7.1",
        "expected_entry_point": "rich/index.html",
    },
    {
        "repo_url": "https://github.com/tiangolo/fastapi.git",
        "project_name": "fastapi",
        "version_tag": "0.111.0",
        "expected_entry_point": "fastapi/index.html",
    },
    {
        "repo_url": "https://github.com/requests/requests.git",
        "project_name": "requests",
        "version_tag": "v2.32.3",
        "expected_entry_point": "requests/index.html",
    },
    {
        "repo_url": "https://github.com/boto/boto3.git",
        "project_name": "boto3",
        "version_tag": "1.34.121",
        "expected_entry_point": "boto3/index.html",
    },
    {
        "repo_url": "https://github.com/django/django.git",
        "project_name": "django",
        "version_tag": "5.0.6",
        "expected_entry_point": "django/index.html",
    },
    {
        "repo_url": "https://github.com/numpy/numpy.git",
        "project_name": "numpy",
        "version_tag": "v2.0.0",
        "expected_entry_point": "numpy/index.html",
    },
    {
        "repo_url": "https://github.com/pallets/click.git",
        "project_name": "click",
        "version_tag": "8.1.7",
        "expected_entry_point": "click/index.html",
    },
    {
        "repo_url": "https://github.com/benjaminp/six.git",
        "project_name": "six",
        "version_tag": "1.16.0",
        "expected_entry_point": "six/index.html",
    },
    {
        "repo_url": "https://github.com/pypa/pipenv.git",
        "project_name": "pipenv",
        "version_tag": "v2024.2.2",
        "expected_entry_point": "pipenv/index.html",
    },
]

TEST_DOCS_OUTPUT_BASE = Path("docset")


@pytest.fixture(scope="session", autouse=True)
def manage_test_output_directory():
    """Fixture to handle output directory."""
    if TEST_DOCS_OUTPUT_BASE.exists():
        shutil.rmtree(TEST_DOCS_OUTPUT_BASE)
    TEST_DOCS_OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    yield


@pytest.mark.parametrize("package_info", PACKAGES_TO_TEST)
def test_documentation_generation_for_package(package_info, tmp_path):
    """Test documentation generation for a package."""
    repo_url = package_info["repo_url"]
    project_name = package_info["project_name"]
    version_tag = package_info.get("version_tag")
    expected_entry_point = package_info.get("expected_entry_point")

    test_clone_base_path = tmp_path / "cloned_projects"
    test_clone_base_path.mkdir()
    test_venv_base_path = tmp_path / "venvs"
    test_venv_base_path.mkdir()

    print(
        f"\n[Testing] Pacchetto: {project_name}, Versione: {version_tag or 'default'}"
    )
    print(f"Output Base Docs: {TEST_DOCS_OUTPUT_BASE.resolve()}")
    print(f"Clone Base Path (temp): {test_clone_base_path.resolve()}")
    print(f"Venv Base Path (temp): {test_venv_base_path.resolve()}")
    doc_generator = DocStringsSrc()
    try:
        doc_generator.run(url=repo_url, project_name=project_name)
    except Exception as e:
        pytest.fail(
            f"L'esecuzione di doc_pipeline.run per {project_name} ha fallito con "
            f"un'eccezione: {e}\n"
            f"Controlla i log precedenti per dettagli."
        )

    final_project_version_docs_dir = TEST_DOCS_OUTPUT_BASE / project_name

    assert final_project_version_docs_dir.exists(), (
        "La directory finale della documentazione versionata non esiste: "
        f"{final_project_version_docs_dir}"
    )
    assert final_project_version_docs_dir.is_dir(), (
        "Il percorso della documentazione versionata non è una directory: "
        f"{final_project_version_docs_dir}"
    )

    html_files = list(final_project_version_docs_dir.rglob("*.html"))
    assert (
        len(html_files) > 0
    ), f"Nessun file HTML trovato in: {final_project_version_docs_dir}"
    print(f"Trovati {len(html_files)} file HTML in {final_project_version_docs_dir}.")

    if expected_entry_point:
        # expected_entry_point è relativo alla directory della versione del progetto
        # Esempio: se final_project_version_docs_dir è 'test_generated_docs/black/24.4.2'
        # e expected_entry_point è 'black/index.html',
        # il file completo sarà 'test_generated_docs/black/24.4.2/black/index.html'
        entry_point_file = final_project_version_docs_dir / expected_entry_point
        assert (
            entry_point_file.exists()
        ), f"Il file di entry point HTML atteso non è stato trovato: {entry_point_file}"
        assert (
            entry_point_file.is_file()
        ), f"Il percorso dell'entry point HTML atteso non è un file: {entry_point_file}"
        print(f"Trovato entry point HTML atteso: {entry_point_file}")
