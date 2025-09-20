"""test docstrings."""

import logging
from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock import MockerFixture

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


def test_build_pdoc_command_no_modules(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _build_pdoc_command handles no modules to document."""
    doc_generator = DocStringsSrc(output_dir=str(tmp_path))

    with caplog.at_level(logging.ERROR):
        command = doc_generator._build_pdoc_command(
            python_executable="/usr/bin/python",
            modules_to_document=[],  # Empty list
            output_directory=tmp_path / "output",
        )

    assert command == []
    assert "DocstringsSrc: No module specified for PDOC." in caplog.text


def test_generate_docs_from_folder_non_existent_input_folder(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify generate_docs_from_folder handles non-existent input folder."""
    doc_generator = DocStringsSrc(output_dir=str(tmp_path))

    non_existent_folder = tmp_path / "non_existent_project"

    with caplog.at_level(logging.ERROR):
        result = doc_generator.generate_docs_from_folder(
            project_name="test_project",
            input_folder=str(non_existent_folder),
            output_folder=str(tmp_path / "output"),
        )

    assert result is False
    assert (
        "DocstringsSrc: The Specified Source Project Folder does not exist"
        in caplog.text
    )


def test_build_pdoc_command_with_template_dir(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _build_pdoc_command includes template_dir when provided."""
    template_dir = tmp_path / "my_template"
    template_dir.mkdir()
    doc_generator = DocStringsSrc(template_dir=template_dir, output_dir=str(tmp_path))

    with caplog.at_level(logging.INFO):
        command = doc_generator._build_pdoc_command(
            python_executable="/usr/bin/python",
            modules_to_document=["my_module"],
            output_directory=tmp_path / "output",
        )

    assert "--template-dir" in command
    assert str(template_dir.resolve()) in command
    assert "Using customized template directory" in caplog.text


def test_handle_successful_doc_move_existing_destination(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Verify _handle_successful_doc_move cleans up existing destination."""
    doc_generator = DocStringsSrc(output_dir=str(tmp_path))

    generated_content_path = tmp_path / "generated_content"
    generated_content_path.mkdir()
    (generated_content_path / "file.html").touch()

    final_docs_destination = tmp_path / "final_docs"
    final_docs_destination.mkdir()
    (final_docs_destination / "old_file.html").touch()  # Existing content

    mock_cleanup_folder = mocker.patch.object(doc_generator, "cleanup_folder")
    mock_shutil_move = mocker.patch("shutil.move")

    doc_generator._handle_successful_doc_move(
        str(generated_content_path), final_docs_destination
    )

    mock_cleanup_folder.assert_called_once_with(final_docs_destination)
    mock_shutil_move.assert_called_once()


def test_cleanup_pdoc_output_on_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    """Verify that _cleanup_pdoc_output_on_failure removes the correct directories."""
    doc_generator = DocStringsSrc(output_dir=str(tmp_path))

    pdoc_command_output_dir = tmp_path / "pdoc_output"
    project_specific_output_dir = pdoc_command_output_dir / "test_project"
    project_specific_output_dir.mkdir(parents=True)
    (project_specific_output_dir / "index.html").touch()

    mock_rmtree = mocker.patch("shutil.rmtree")

    doc_generator._cleanup_pdoc_output_on_failure(
        pdoc_command_output_dir, "test_project"
    )

    mock_rmtree.assert_called_once_with(project_specific_output_dir)


def test_find_and_report_non_package_folders(tmp_path: Path) -> None:
    """Verify that find and report non-package folders identifies non-package one."""
    doc_generator = DocStringsSrc(output_dir=str(tmp_path))

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "__init__.py").touch()
    (project_root / "module.py").touch()

    non_package_folder = project_root / "non_package"
    non_package_folder.mkdir()
    (non_package_folder / "file.txt").touch()

    report_file = tmp_path / "report.txt"

    doc_generator._find_and_report_non_package_folders(
        scan_base_path=project_root,
        project_root_for_relative_paths=project_root,
        output_report_file=report_file,
    )

    assert report_file.exists()
    with open(report_file) as f:
        content = f.read()
        assert "- non_package" in content


def test_process_reported_folders(tmp_path: Path, mocker: MockerFixture) -> None:
    """Verify that _process_reported_folders removes reported folders and links."""
    doc_generator = DocStringsSrc(output_dir=str(tmp_path))

    pdoc_project_output_path = tmp_path / "pdoc_output"
    pdoc_project_output_path.mkdir()

    reported_folder = pdoc_project_output_path / "reported_folder"
    reported_folder.mkdir()
    (reported_folder / "file.txt").touch()

    html_file = pdoc_project_output_path / "index.html"
    html_file.write_text('<a href="reported_folder/file.txt">link</a>')

    report_file = tmp_path / "report.txt"
    report_file.write_text("- reported_folder")

    mocker.patch.object(
        doc_generator, "_read_non_package_report", return_value=["reported_folder"]
    )
    mock_rmtree = mocker.patch("shutil.rmtree")
    mock_clean_html = mocker.patch.object(
        doc_generator, "_clean_html_file_for_reported_path"
    )

    doc_generator._process_reported_folders(report_file, pdoc_project_output_path)

    mock_rmtree.assert_called_once_with(reported_folder)
    mock_clean_html.assert_called_once()


def test_attempt_install_missing_dependency(mocker: MockerFixture) -> None:
    """Verify that _attempt_install_missing_dependency correctly calls pip."""
    doc_generator = DocStringsSrc()
    mock_execute = mocker.patch(
        "devildex.docstrings.docstrings_src.execute_command", return_value=("", "", 0)
    )

    result = doc_generator._attempt_install_missing_dependency(
        "requests", "/usr/bin/python"
    )

    assert result is True
    mock_execute.assert_called_once_with(
        [
            "/usr/bin/python",
            "-m",
            "pip",
            "install",
            "requests",
        ],
        "Install missing dependency requests",
    )


def test_is_pdoc_dummy_module(mocker: MockerFixture) -> None:
    """Verify _is_pdoc_dummy_module correctly identifies dummy modules."""
    doc_generator = DocStringsSrc()

    # Case 1: None module
    assert doc_generator._is_pdoc_dummy_module(None, "any_module") is True

    # Case 2: Module without __file__ or __path__
    mock_module_no_attrs = mocker.MagicMock()
    del mock_module_no_attrs.__file__
    del mock_module_no_attrs.__path__
    mock_module_no_attrs.__name__ = "dummy_module"
    assert (
        doc_generator._is_pdoc_dummy_module(mock_module_no_attrs, "dummy_module")
        is True
    )

    # Case 3: Module with __file__ (real module)
    mock_real_module = mocker.MagicMock()
    mock_real_module.__file__ = "/path/to/real_module.py"
    mock_real_module.__name__ = "real_module"
    assert doc_generator._is_pdoc_dummy_module(mock_real_module, "real_module") is False

    # Case 4: Module with __path__ (real package)
    mock_real_package = mocker.MagicMock()
    mock_real_package.__path__ = ["/path/to/real_package"]
    mock_real_package.__name__ = "real_package"
    assert (
        doc_generator._is_pdoc_dummy_module(mock_real_package, "real_package") is False
    )

    # Case 5: Module with __name__ not matching expected_name
    mock_module_wrong_name = mocker.MagicMock()
    mock_module_wrong_name.__file__ = "/path/to/file.py"
    mock_module_wrong_name.__name__ = "wrong_name"
    assert (
        doc_generator._is_pdoc_dummy_module(mock_module_wrong_name, "expected_name")
        is False
    )


def test_log_traceback(mocker: MockerFixture, caplog: pytest.LogCaptureFixture) -> None:
    """Verify _log_traceback logs a debug message with exc_info."""
    doc_generator = DocStringsSrc()
    mock_logger_debug = mocker.patch("devildex.docstrings.docstrings_src.logger.debug")

    with caplog.at_level(logging.DEBUG):
        try:
            raise ValueError("Test exception")
        except ValueError:
            doc_generator._log_traceback()

    mock_logger_debug.assert_called_once_with("Traceback:", exc_info=True)
