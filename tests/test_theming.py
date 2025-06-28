"""module that tests theming features."""

import logging
import shutil
import webbrowser
from pathlib import Path

import pytest

from devildex.docstrings.docstrings_src import DocStringsSrc
from devildex.info import PROJECT_ROOT
from devildex.readthedocs.readthedocs_src import build_sphinx_docs
from devildex.theming.manager import ThemeManager
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command,
    install_project_and_dependencies_in_venv,
)

ORIGINAL_DUMMY_PROJECT_PATH = PROJECT_ROOT / "tests" / "dummy_project"
PDOC3_THEME_SOURCE = (
    PROJECT_ROOT / "src" / "devildex" / "theming" / "devildex_pdoc3_theme"
)
PYDOCTOR_THEME_SOURCE = (
    PROJECT_ROOT / "src" / "devildex" / "theming" / "devildex_pydoctor_theme"
)
logger = logging.getLogger(__name__)


@pytest.fixture
def dummy_project_in_tmp_path(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Fixture that copies the content of 'Tests/dummy_project' in one.

    tmp_path subdirectory and returns the path to this copy.
    """
    create_nested_structure = getattr(request, "param", False)
    project_source_name = ORIGINAL_DUMMY_PROJECT_PATH.name
    if create_nested_structure:
        base_dir_name = "base_dir"
        container_path = tmp_path / base_dir_name
        actual_project_copy_destination = container_path / project_source_name
        if actual_project_copy_destination.exists():
            shutil.rmtree(actual_project_copy_destination)
        shutil.copytree(ORIGINAL_DUMMY_PROJECT_PATH, actual_project_copy_destination)
        return container_path
    else:
        direct_project_copy_destination = tmp_path / project_source_name
        if direct_project_copy_destination.exists():
            shutil.rmtree(direct_project_copy_destination)
        shutil.copytree(ORIGINAL_DUMMY_PROJECT_PATH, direct_project_copy_destination)

        return direct_project_copy_destination


@pytest.mark.focus
def test_sphinx_theme(dummy_project_in_tmp_path: Path) -> None:
    """Test applying a sphinx theme."""
    conf_path = Path(dummy_project_in_tmp_path / "docs" / "source" / "conf.py")
    t_man = ThemeManager(
        dummy_project_in_tmp_path, "sphinx", sphinx_conf_file=conf_path
    )
    sphinx_source_dir = dummy_project_in_tmp_path / "docs" / "source"
    t_man.sphinx_change_conf()
    project_slug_for_build = "dummy_project_test"
    version_identifier_for_build = "local_test"
    test_base_output_directory = dummy_project_in_tmp_path / "test_sphinx_build_output"
    output_html_dir_str = build_sphinx_docs(
        isolated_source_path=str(sphinx_source_dir.resolve()),
        project_slug=project_slug_for_build,
        version_identifier=version_identifier_for_build,
        original_clone_dir_path=str(dummy_project_in_tmp_path.resolve()),
        base_output_dir=test_base_output_directory,
    )

    output_html_dir = Path(output_html_dir_str)
    index_html_path = output_html_dir / "index.html"

    url_to_open = index_html_path.as_uri()
    logger.info(f"🔗 Apri manually questo URI: {url_to_open}\n")
    webbrowser.open_new_tab(url_to_open)


# In tests/test_theming.py


@pytest.mark.parametrize("dummy_project_in_tmp_path", [True], indirect=True)
def test_pdoc3_theme(dummy_project_in_tmp_path: Path) -> None:
    """Test applying a pdoc3 theme."""
    doc_generator = DocStringsSrc(template_dir=PDOC3_THEME_SOURCE)
    pdoc_build_root_dir = dummy_project_in_tmp_path / "pdoc3_docs_output"
    project_root_for_pdoc3 = dummy_project_in_tmp_path  # This is .../base_dir
    pdoc_build_root_dir.mkdir(parents=True, exist_ok=True)

    output_content_path_str = doc_generator.generate_docs_from_folder(
        project_name="dummy_project",
        input_folder=str(project_root_for_pdoc3.resolve()),
        output_folder=str(pdoc_build_root_dir.resolve()),
    )

    assert (
        output_content_path_str
    ), "Documentation generation failed, returned False or None"
    assert isinstance(
        output_content_path_str, str
    ), f"Expected a path string, got {type(output_content_path_str)}"

    output_content_path = Path(output_content_path_str)
    entry_html_path: Path | None = None

    if output_content_path.is_dir():
        entry_html_path = output_content_path / "index.html"
    elif output_content_path.is_file():
        assert (
            output_content_path.name == "dummy_project.html"
        ), f"Expected dummy_project.html, got {output_content_path.name}"
        entry_html_path = output_content_path
    else:
        pytest.fail(
            f"Output path {output_content_path} from generate_docs_from_folder "
            "is neither a file nor a directory."
        )

    assert (
        entry_html_path.exists()
    ), f"Expected entry HTML file {entry_html_path} does not exist"
    assert (
        entry_html_path.is_file()
    ), f"Expected entry HTML path {entry_html_path} is not a file"

    if doc_generator.template_dir:
        static_dir_expected_location = entry_html_path.parent / "static"
        if output_content_path.is_dir():
            static_dir_expected_location = output_content_path / "static"

        assert static_dir_expected_location.exists(), (
            f"Static directory {static_dir_expected_location} not "
            "found for themed output."
        )
        assert (
            static_dir_expected_location.is_dir()
        ), f"Static path {static_dir_expected_location} is not a directory."

    url_to_open = entry_html_path.as_uri()
    logger.info(f"🔗 Open manually this URI: {url_to_open}\n")
    webbrowser.open_new_tab(url_to_open)


def _minimal_build_pydoctor_docs(
    project_name_for_pydoctor: str,
    qualified_module_to_document: str,
    source_project_path: Path,
    pydoctor_build_root_output_dir: Path,
) -> str | None:
    actual_docs_output_dir = pydoctor_build_root_output_dir
    if actual_docs_output_dir.exists():
        shutil.rmtree(actual_docs_output_dir)
    actual_docs_output_dir.mkdir(parents=True, exist_ok=True)

    with IsolatedVenvManager(
        project_name=f"pydoctor_test_{project_name_for_pydoctor}"
    ) as i_venv:
        install_project_and_dependencies_in_venv(
            pip_executable=i_venv.pip_executable,
            project_name=project_name_for_pydoctor,
            project_root_for_install=source_project_path,
            doc_requirements_path=None,
            base_packages_to_install=["pydoctor"],
        )

        pydoctor_command = [
            i_venv.python_executable,
            "-m",
            "pydoctor",
            f"--project-name={project_name_for_pydoctor}",
            f"--html-output={pydoctor_build_root_output_dir.resolve()!s}",
            f"--template-dir={PYDOCTOR_THEME_SOURCE.resolve()!s}",
            qualified_module_to_document,
        ]

        _stdout, _stderr, return_code = execute_command(
            pydoctor_command, "PyDoctor Build", cwd=source_project_path
        )
        index_html_path = actual_docs_output_dir / "index.html"
        if return_code == 0 and index_html_path.exists():
            return str(actual_docs_output_dir.resolve())
    return None


@pytest.mark.parametrize("dummy_project_in_tmp_path", [True], indirect=True)
def test_pydoctor_theme(dummy_project_in_tmp_path: Path) -> None:
    """Test applying a pydoctor theme."""
    project_name_for_pydoctor_docs = "DummyPyDoc"
    module_file_to_doc_pydoctor = "dummy_project"
    pydoctor_build_root_dir = dummy_project_in_tmp_path / "pydoctor_docs_output"
    project_root_for_pydoctor = dummy_project_in_tmp_path

    output_project_docs_path_str = _minimal_build_pydoctor_docs(
        project_name_for_pydoctor=project_name_for_pydoctor_docs,
        qualified_module_to_document=module_file_to_doc_pydoctor,
        source_project_path=project_root_for_pydoctor,
        pydoctor_build_root_output_dir=pydoctor_build_root_dir,
    )

    output_project_docs_path = Path(output_project_docs_path_str)
    index_html_path = output_project_docs_path / "index.html"

    url_to_open = index_html_path.as_uri()
    logger.info("🔗 Apri manually questo URI: %s", url_to_open)
    webbrowser.open_new_tab(url_to_open)
