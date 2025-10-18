"""test orchestrator module."""

import shutil
import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.database.models import PackageDetails
from devildex.orchestrator.documentation_orchestrator import Orchestrator

PACKAGES_TO_TEST = [
    {
        "details_data": {
            "name": "black",
            "version": "24.4.2",
            "project_urls": {
                "Source Code": "https://github.com/psf/black.git",
                "Documentation": "https://black.readthedocs.io/",
            },
            "vcs_url": "https://github.com/psf/black.git",
            "rtd_url": "https://black.readthedocs.io/",
        },
        "repo_url_for_clone": "https://github.com/psf/black.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "flask",
            "version": "3.0.3",
            "project_urls": {
                "Source Code": "https://github.com/pallets/flask.git",
                "Documentation": "https://flask.palletsprojects.com/",
            },
            "vcs_url": "https://github.com/pallets/flask.git",
            "rtd_url": "https://flask.palletsprojects.com/",
        },
        "repo_url_for_clone": "https://github.com/pallets/flask.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "pytest",
            "version": "8.1.1",
            "project_urls": {
                "Source Code": "https://github.com/pytest-dev/pytest.git",
                "Documentation": "https://docs.pytest.org/",
            },
            "vcs_url": "https://github.com/pytest-dev/pytest.git",
            "rtd_url": "https://docs.pytest.org/",
        },
        "repo_url_for_clone": "https://github.com/pytest-dev/pytest.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "project-slug-intended-to-fail-rtd",
            "version": "1.0.0",
            "project_urls": {
                "Source Code": "https://github.com/psf/black.git",
                "Documentation": "https://this-rtd-project-should-not-exist.readthedocs.io/",
            },
            "vcs_url": "https://github.com/psf/black.git",
            "rtd_url": "https://this-rtd-project-should-not-exist.readthedocs.io/",
        },
        "repo_url_for_clone": "https://github.com/psf/black.git",
        "expected_preferred_type": "sphinx",
        "expect_grab_success": True,
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "rich",
            "version": "13.7.1",
            "project_urls": {
                "Source Code": "https://github.com/Textualize/rich.git",
            },
            "vcs_url": "https://github.com/Textualize/rich.git",
        },
        "repo_url_for_clone": "https://github.com/Textualize/rich.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "fastapi",
            "version": "0.111.0",
            "project_urls": {
                "Source Code": "https://github.com/tiangolo/fastapi.git",
            },
            "vcs_url": "https://github.com/tiangolo/fastapi.git",
        },
        "repo_url_for_clone": "https://github.com/tiangolo/fastapi.git",
        "expected_preferred_type": "docstrings",
        "expected_entry_point": "index.html",
        "expect_grab_success": False,
    },
    {
        "details_data": {
            "name": "requests",
            "version": "2.31.0",
            "project_urls": {
                "Source Code": "https://github.com/requests/requests.git",
                "Documentation": "https://requests.readthedocs.io/",
            },
            "vcs_url": "https://github.com/requests/requests.git",
            "rtd_url": "https://requests.readthedocs.io/",
        },
        "repo_url_for_clone": "https://github.com/requests/requests.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "django",
            "version": "5.0.4",
            "project_urls": {
                "Source Code": "https://github.com/django/django.git",
                "Documentation": "https://docs.djangoproject.com/",
            },
            "vcs_url": "https://github.com/django/django.git",
            "rtd_url": "https://docs.djangoproject.com/",
        },
        "repo_url_for_clone": "https://github.com/django/django.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "numpy",
            "version": "1.26.4",
            "project_urls": {
                "Source Code": "https://github.com/numpy/numpy.git",
                "Documentation": "https://numpy.org/doc/",
            },
            "vcs_url": "https://github.com/numpy/numpy.git",
            "rtd_url": "https://numpy.org/doc/",
        },
        "repo_url_for_clone": "https://github.com/numpy/numpy.git",
        "expected_preferred_type": "sphinx",
        "expect_grab_success": False,
    },
    {
        "details_data": {
            "name": "click",
            "version": "8.1.7",
            "project_urls": {
                "Source Code": "https://github.com/pallets/click.git",
                "Documentation": "https://click.palletsprojects.com/",
            },
            "vcs_url": "https://github.com/pallets/click.git",
            "rtd_url": "https://click.palletsprojects.com/",
        },
        "repo_url_for_clone": "https://github.com/pallets/click.git",
        "expected_preferred_type": "sphinx",
        "expect_grab_success": False,
    },
    {
        "details_data": {
            "name": "six",
            "version": "1.16.0",
            "project_urls": {
                "Source Code": "https://github.com/benjaminp/six.git",
                "Documentation": "https://six.readthedocs.io/",
            },
            "vcs_url": "https://github.com/benjaminp/six.git",
            "rtd_url": "https://six.readthedocs.io/",
        },
        "repo_url_for_clone": "https://github.com/benjaminp/six.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "pipenv",
            "version": "2023.12.1",
            "project_urls": {
                "Source Code": "https://github.com/pypa/pipenv.git",
                "Documentation": "https://pipenv.pypa.io/",
            },
            "vcs_url": "https://github.com/pypa/pipenv.git",
            "rtd_url": "https://pipenv.pypa.io/",
        },
        "repo_url_for_clone": "https://github.com/pypa/pipenv.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "details_data": {
            "name": "mkdocs",
            "version": "1.6.0",
            "project_urls": {
                "Source Code": "https://github.com/mkdocs/mkdocs.git",
                "Documentation": "https://www.mkdocs.org/",
            },
            "vcs_url": "https://github.com/mkdocs/mkdocs.git",
            "rtd_url": "https://www.mkdocs.org/",
        },
        "repo_url_for_clone": "https://github.com/mkdocs/mkdocs.git",
        "expected_preferred_type": "mkdocs",
        "expected_entry_point": "index.html",
        "expect_grab_success": True,
    },
]

GIT_FULL_PATH = shutil.which("git")


orchestrator_test_params = [
    pytest.param(package_config, id=package_config["details_data"]["name"])
    for package_config in PACKAGES_TO_TEST
]


def _setup_test_environment(package_config: dict, tmp_path: Path) -> tuple[Path, Path]:
    """Set up the test environment by cloning the repo and creating output dirs."""
    repo_url_for_clone = package_config["repo_url_for_clone"]
    package_name_for_paths = package_config["details_data"]["name"]
    clone_target_dir = tmp_path / f"source_clone_{package_name_for_paths}"
    orchestrator_base_output_for_test = (
        tmp_path / f"orchestrator_output_{package_name_for_paths}"
    )

    subprocess.run(  # noqa: S603
        [
            GIT_FULL_PATH,
            "clone",
            "--depth",
            "1",
            repo_url_for_clone,
            str(clone_target_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return clone_target_dir, orchestrator_base_output_for_test


def _run_orchestrator(
    package_details: PackageDetails, base_output_dir: Path
) -> tuple[Orchestrator, str]:
    """Instantiate and run the orchestrator."""
    orchestrator = Orchestrator(
        package_details=package_details,
        base_output_dir=base_output_dir,
    )
    orchestrator.start_scan()
    detected_doc_type = orchestrator.get_detected_doc_type()
    return orchestrator, detected_doc_type


def _assert_success(
    orchestrator: Orchestrator,
    package_details: PackageDetails,
    detected_doc_type: str,
    expected_entry_point: str,
) -> None:
    """Assert that the documentation retrieval was successful."""
    output_docs_root_path_str = orchestrator.grab_build_doc()
    operation_result = orchestrator.get_last_operation_result()

    assert operation_result is not False, (
        f"Orchestrator's grab_build_doc failed for {package_details.name} "
        f"(detected type: {detected_doc_type}). Result: {operation_result}"
    )
    assert isinstance(operation_result, str), (
        f"Expected a path string from successful grab_build_doc for "
        f"{package_details.name}, got {type(operation_result)}. "
        f"Value: {operation_result}"
    )
    assert output_docs_root_path_str == operation_result, (
        f"Return value of grab_build_doc ('{output_docs_root_path_str}') "
        f"and last_operation_result ('{operation_result}') "
        f"mismatch for {package_details.name}."
    )

    output_docs_root_path = Path(output_docs_root_path_str)
    assert output_docs_root_path.exists(), (
        f"Output path '{output_docs_root_path}' from Orchestrator "
        f"does not exist for {package_details.name}"
    )
    assert output_docs_root_path.is_dir(), (
        f"Output path '{output_docs_root_path}' from Orchestrator "
        f"is not a directory for {package_details.name}"
    )
    assert expected_entry_point is not None, (
        "expected_entry_point_filename is missing in test config for "
        f"{package_details.name} when success is expected."
    )
    final_entry_point_path = output_docs_root_path / expected_entry_point
    assert final_entry_point_path.is_file(), (
        f"Expected entry point '{final_entry_point_path}' not found or is not a file "
        f"for {package_details.name} (type: {detected_doc_type})"
    )

    html_files = list(output_docs_root_path.glob("**/*.html"))
    assert len(html_files) > 0, (
        f"No HTML files found in output for {package_details.name} "
        f"at {output_docs_root_path}"
    )


def _assert_failure(
    orchestrator: Orchestrator, package_details: PackageDetails
) -> None:
    """Assert that the documentation retrieval failed."""
    output_docs_root_path_str = orchestrator.grab_build_doc()
    operation_result = orchestrator.get_last_operation_result()

    assert operation_result is False, (
        "Expected grab_build_doc to result in False for "
        f"{package_details.name} due to expect_success=False. "
        f"Got: {operation_result} (type: {type(operation_result)})"
    )
    assert output_docs_root_path_str is False, (
        "Expected grab_build_doc to return None for "
        f"{package_details.name} due to expected failure, but got: "
        f"{output_docs_root_path_str}"
    )


@pytest.mark.parametrize("package_config", orchestrator_test_params)
def test_orchestrator_documentation_retrieval(
    package_config: dict, tmp_path: Path, mocker: MockerFixture
) -> None:
    """Test orchestrator retrieval."""
    if package_config["details_data"]["name"] == "fastapi":
        return

    clone_target_dir, orchestrator_base_output_for_test = _setup_test_environment(
        package_config, tmp_path
    )

    details_data_from_config = package_config["details_data"].copy()
    details_data_from_config["initial_source_path"] = str(clone_target_dir)
    package_details_for_test = PackageDetails.from_dict(details_data_from_config)

    orchestrator, detected_doc_type = _run_orchestrator(
        package_details_for_test, orchestrator_base_output_for_test
    )

    expected_preferred_doc_type = package_config["expected_preferred_type"]
    assert detected_doc_type == expected_preferred_doc_type, (
        f"For {package_details_for_test.name}, expected preferred type "
        f"'{expected_preferred_doc_type}' but Orchestrator detected "
        f"'{detected_doc_type}'"
    )

    if detected_doc_type == "mkdocs":
        mock_mkdocs_builder_generate_docset = mocker.patch(
            "devildex.grabbers.mkdocs_builder.MkDocsBuilder.generate_docset",
            return_value="mock_mkdocs_output_path",
        )
        output_docs_root_path_str = orchestrator.grab_build_doc()
        mock_mkdocs_builder_generate_docset.assert_called_once()
        assert output_docs_root_path_str == "mock_mkdocs_output_path"
        operation_result = orchestrator.get_last_operation_result()
        assert operation_result == "mock_mkdocs_output_path"
    else:
        expect_success = package_config.get("expect_grab_success", True)
        if expect_success:
            expected_entry_point_filename = package_config.get("expected_entry_point")
            _assert_success(
                orchestrator,
                package_details_for_test,
                detected_doc_type,
                expected_entry_point_filename,
            )
        else:
            _assert_failure(orchestrator, package_details_for_test)
