import subprocess
from pathlib import Path

import pytest

from devildex.models import PackageDetails
from devildex.orchestrator.documentation_orchestrator import Orchestrator

PACKAGES_TO_TEST = [
    {
        "details_data": {
            "name": "black",
            "version": "24.4.2", # Versione specifica per il test del fetcher
            "project_urls": {
                "Source Code": "https://github.com/psf/black.git",
                "Documentation": "https://black.readthedocs.io/",
            },
            # vcs_url e rtd_url possono essere qui o derivati/sovrascritti nel test
            "vcs_url": "https://github.com/psf/black.git",
            "rtd_url": "https://black.readthedocs.io/",
        },
        "repo_url_for_clone": "https://github.com/psf/black.git", # Usato per il clone iniziale nel test
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html"
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
                "Source Code": "https://github.com/psf/black.git", # Sorgente valido
                "Documentation": "https://this-rtd-project-should-not-exist.readthedocs.io/",
            },
            "vcs_url": "https://github.com/psf/black.git", # Sorgente valido
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
            # rtd_url può essere omesso se non c'è, PackageDetails userà None
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
        "expect_grab_success": False
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
        "expect_grab_success": False
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
]


@pytest.mark.parametrize("package_config", PACKAGES_TO_TEST)
def test_orchestrator_documentation_retrieval(package_config, tmp_path):
    details_data_from_config = package_config["details_data"].copy()
    repo_url_for_clone = package_config["repo_url_for_clone"]
    expected_preferred_doc_type = package_config["expected_preferred_type"]
    expected_entry_point_filename = package_config.get("expected_entry_point")
    expect_success = package_config.get("expect_grab_success", True)

    package_name_for_paths = details_data_from_config['name']
    clone_target_dir = tmp_path / f"source_clone_{package_name_for_paths}"
    print(f"\nCloning {repo_url_for_clone} to {clone_target_dir} for package {package_name_for_paths}...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url_for_clone, str(clone_target_dir)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Git clone failed for {repo_url_for_clone}: {e.stderr}")
    except FileNotFoundError:
        pytest.fail("Git command not found. Ensure git is installed and in PATH.")

    orchestrator_base_output_for_test = tmp_path / f"orchestrator_output_{package_name_for_paths}"
    details_data_from_config["initial_source_path"] = str(clone_target_dir)
    package_details_for_test = PackageDetails.from_dict(details_data_from_config)
    print(f"Initializing Orchestrator for {package_details_for_test.name} at {clone_target_dir}")
    orchestrator = Orchestrator(
        package_details=package_details_for_test,
        base_output_dir=orchestrator_base_output_for_test
    )

    orchestrator.start_scan()
    detected_doc_type = orchestrator.get_detected_doc_type()
    print(
        f"Project: {package_details_for_test.name}, Detected documentation type by "
        f"Orchestrator: {detected_doc_type}"
    )

    assert (
        detected_doc_type == expected_preferred_doc_type
    ), f"For {package_details_for_test.name}, expected preferred type '{expected_preferred_doc_type}'"
    f" but Orchestrator detected '{detected_doc_type}'"

    print(
        f"Orchestrator attempting to grab/build docs for {package_details_for_test.name} "
        f"using type: {detected_doc_type}..."
    )
    output_docs_root_path_str = orchestrator.grab_build_doc()
    print(
        "DEBUG: Path returned by grab_build_doc for "
        f"{package_details_for_test.name}: {output_docs_root_path_str}"
    )

    operation_result = orchestrator.get_last_operation_result()

    print(
        f"Project: {package_details_for_test.name}, Orchestrator grab_build_doc result:"
        f" {operation_result}, Output path from return: {output_docs_root_path_str}"
    )

    if expect_success:
        assert (
            operation_result is not False
        ), f"Orchestrator's grab_build_doc failed for {package_details_for_test.name} "
        f"(detected type: {detected_doc_type}). Result: {operation_result}"
        assert isinstance(
            operation_result, str
        ), f"Expected a path string from successful grab_build_doc for {package_details_for_test.name},"
        f" got {type(operation_result)}. Value: {operation_result}"
        assert (
            output_docs_root_path_str == operation_result
        ), f"Return value of grab_build_doc ('{output_docs_root_path_str}')"
        f" and last_operation_result ('{operation_result}')"
        f" mismatch for {package_details_for_test.name}."

        output_docs_root_path = Path(output_docs_root_path_str)
        assert (
            output_docs_root_path.exists()
        ), f"Output path '{output_docs_root_path}' from Orchestrator"
        f" does not exist for {package_details_for_test.name}"
        assert (
            output_docs_root_path.is_dir()
        ), f"Output path '{output_docs_root_path}' from "
        f"Orchestrator is not a directory for {package_details_for_test.name}"

        assert (
            expected_entry_point_filename is not None
        ), "expected_entry_point_filename is missing in test "
        f"config for {package_details_for_test.name} when success is expected."
        final_entry_point_path = output_docs_root_path / expected_entry_point_filename
        assert (
            final_entry_point_path.is_file()
        ), f"Expected entry point '{final_entry_point_path}' not found or is not a "
        f"file for {package_details_for_test.name} (type: {detected_doc_type})"

        html_files = list(output_docs_root_path.glob("**/*.html"))
        assert len(html_files) > 0, "No HTML files found in output for "
        f"{package_details_for_test.name} at {output_docs_root_path}"
    else:
        assert (
            operation_result is None
        ), f"Expected grab_build_doc to result in None for {package_details_for_test.name} due to "
        f"expected failure, but got type {type(operation_result)}"
        f" with value: {operation_result}"
        assert (
            output_docs_root_path_str is None
        ), f"Expected grab_build_doc to return None for {package_details_for_test.name} "
        f"due to expected failure, but got: {output_docs_root_path_str}"

    print(
        f"Successfully processed and verified {package_details_for_test.name} with "
        "type {detected_doc_type}."
    )
