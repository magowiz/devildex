import pytest
from pathlib import Path
import subprocess


from devildex.orchestrator.documentation_orchestrator import Orchestrator

PACKAGES_TO_TEST = [
    {
        "repo_url": "https://github.com/psf/black.git",
        "project_name": "black",
        "project_url": "https://github.com/psf/black.git",
        "rtd_url": "https://black.readthedocs.io/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/pallets/flask.git",
        "project_name": "flask",
        "project_url": "https://github.com/pallets/flask.git",
        "rtd_url": "https://flask.palletsprojects.com/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/pytest-dev/pytest.git",
        "project_name": "pytest",
        "project_url": "https://github.com/pytest-dev/pytest.git",
        "rtd_url": "https://docs.pytest.org/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/psf/black.git",
        "project_name": "project-slug-intended-to-fail-rtd",
        "project_url": "https://github.com/psf/black.git",
        "rtd_url": "https://this-rtd-project-should-not-exist.readthedocs.io/",
        "expected_preferred_type": "sphinx",
        "expect_grab_success": False,
    },
    {
        "repo_url": "https://github.com/Textualize/rich.git",
        "project_name": "rich",
        "project_url": "https://github.com/Textualize/rich.git",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/tiangolo/fastapi.git",
        "project_name": "fastapi",
        "project_url": "https://github.com/tiangolo/fastapi.git",
        "expected_preferred_type": "docstrings",
        "expected_entry_point": "fastapi/index.html",
    },
    {
        "repo_url": "https://github.com/requests/requests.git",
        "project_name": "requests",
        "project_url": "https://github.com/requests/requests.git",
        "rtd_url": "https://requests.readthedocs.io/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/django/django.git",
        "project_name": "django",
        "project_url": "https://github.com/django/django.git",
        "rtd_url": "https://docs.djangoproject.com/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/numpy/numpy.git",
        "project_name": "numpy",
        "project_url": "https://github.com/numpy/numpy.git",
        "rtd_url": "https://numpy.org/doc/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/pallets/click.git",
        "project_name": "click",
        "project_url": "https://github.com/pallets/click.git",
        "rtd_url": "https://click.palletsprojects.com/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/benjaminp/six.git",
        "project_name": "six",
        "project_url": "https://github.com/benjaminp/six.git",
        "rtd_url": "https://six.readthedocs.io/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
    {
        "repo_url": "https://github.com/pypa/pipenv.git",
        "project_name": "pipenv",
        "project_url": "https://github.com/pypa/pipenv.git",
        "rtd_url": "https://pipenv.pypa.io/",
        "expected_preferred_type": "sphinx",
        "expected_entry_point": "index.html",
    },
]


@pytest.mark.parametrize("package_info", PACKAGES_TO_TEST)
def test_orchestrator_documentation_retrieval(package_info, tmp_path):
    repo_url = package_info["repo_url"]
    project_name = package_info["project_name"]
    project_url_for_orchestrator = package_info.get("project_url", repo_url)
    rtd_url = package_info.get("rtd_url")
    expected_preferred_doc_type = package_info["expected_preferred_type"]
    expected_entry_point_filename = package_info.get("expected_entry_point")

    clone_target_dir = tmp_path / project_name
    print(f"\nCloning {repo_url}  to {clone_target_dir} for project {project_name}...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(clone_target_dir)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError:
        print("Direct tag clone failed for , trying default branch then checkout...")
    except FileNotFoundError:
        pytest.fail("Git command not found. Ensure git is installed and in PATH.")

    print(f"Initializing Orchestrator for {project_name} at {clone_target_dir}")
    orchestrator = Orchestrator(
        project_name=project_name,
        project_path=str(clone_target_dir),
        rtd_url=rtd_url,
        project_url=project_url_for_orchestrator,
    )

    orchestrator.start_scan()
    detected_doc_type = orchestrator.get_detected_doc_type()
    print(
        f"Project: {project_name}, Detected documentation type by "
        f"Orchestrator: {detected_doc_type}"
    )

    assert (
        detected_doc_type == expected_preferred_doc_type
    ), f"For {project_name}, expected preferred type '{expected_preferred_doc_type}'"
    f" but Orchestrator detected '{detected_doc_type}'"

    print(
        f"Orchestrator attempting to grab/build docs for {project_name} "
        f"using type: {detected_doc_type}..."
    )
    output_docs_root_path_str = orchestrator.grab_build_doc()
    print(
        "DEBUG: Path returned by grab_build_doc for "
        f"{project_name}: {output_docs_root_path_str}"
    )

    operation_result = orchestrator.get_last_operation_result()

    print(
        f"Project: {project_name}, Orchestrator grab_build_doc result:"
        f" {operation_result}, Output path from return: {output_docs_root_path_str}"
    )
    expect_success = package_info.get("expect_grab_success", True)

    if expect_success:
        assert (
            operation_result is not False
        ), f"Orchestrator's grab_build_doc failed for {project_name} "
        f"(detected type: {detected_doc_type}). Result: {operation_result}"
        assert isinstance(
            operation_result, str
        ), f"Expected a path string from successful grab_build_doc for {project_name},"
        f" got {type(operation_result)}. Value: {operation_result}"
        assert (
            output_docs_root_path_str == operation_result
        ), f"Return value of grab_build_doc ('{output_docs_root_path_str}')"
        f" and last_operation_result ('{operation_result}')"
        f" mismatch for {project_name}."

        output_docs_root_path = Path(output_docs_root_path_str)
        assert (
            output_docs_root_path.exists()
        ), f"Output path '{output_docs_root_path}' from Orchestrator"
        f" does not exist for {project_name}"
        assert (
            output_docs_root_path.is_dir()
        ), f"Output path '{output_docs_root_path}' from "
        f"Orchestrator is not a directory for {project_name}"

        assert (
            expected_entry_point_filename is not None
        ), "expected_entry_point_filename is missing in test "
        f"config for {project_name} when success is expected."
        final_entry_point_path = output_docs_root_path / expected_entry_point_filename
        assert (
            final_entry_point_path.is_file()
        ), f"Expected entry point '{final_entry_point_path}' not found or is not a "
        f"file for {project_name} (type: {detected_doc_type})"

        html_files = list(output_docs_root_path.glob("**/*.html"))
        assert (
            len(html_files) > 0
        ), "No HTML files found in output for "
        f"{project_name} at {output_docs_root_path}"
    else:
        assert (
            operation_result is None
        ), f"Expected grab_build_doc to result in None for {project_name} due to "
        f"expected failure, but got type {type(operation_result)}"
        f" with value: {operation_result}"
        assert (
            output_docs_root_path_str is None
        ), f"Expected grab_build_doc to return None for {project_name} "
        f"due to expected failure, but got: {output_docs_root_path_str}"

    print(
        f"Successfully processed and verified {project_name} with "
        "type {detected_doc_type}."
    )
