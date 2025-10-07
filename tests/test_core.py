"""Tests for the DevilDexCore class."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.core import DevilDexCore
from devildex.database.models import PackageDetails

EXPECTED_SCANNED_PACKAGES_NO_EXPLICIT = 3
EXPECTED_RMTEE_CALL_COUNT = 2
EXPECTED_SCANNED_PACKAGES_EXPLICIT = 2


@pytest.fixture
def mock_installed_packages() -> list[PackageDetails]:
    """Provide a list of mock installed packages data as PackageDetails objects."""
    return [
        PackageDetails(name="requests", version="2.25.1", project_urls={}),
        PackageDetails(name="pytest", version="6.2.2", project_urls={}),
        PackageDetails(name="numpy", version="1.20.1", project_urls={}),
    ]


@pytest.fixture
def core(tmp_path: Path, mocker: MockerFixture) -> DevilDexCore:
    """Provide a DevilDexCore instance with its paths mocked with a temp directory."""
    mock_app_paths_class = mocker.patch("devildex.core.AppPaths")
    mock_app_paths_instance = mock_app_paths_class.return_value
    mock_app_paths_instance.docsets_base_dir = tmp_path / "docsets"
    mock_app_paths_instance.database_path = tmp_path / "devildex_test.db"
    mocker.patch.dict("os.environ", {"DEVILDEX_DEV_MODE": "0"})
    instance = DevilDexCore()
    return instance

@pytest.fixture
def core_with_db(tmp_path: Path, mocker: MockerFixture, db_connection_and_tables) -> DevilDexCore:
    """Provide a DevilDexCore instance with a file-based database."""
    db_url, _, _ = db_connection_and_tables
    mock_app_paths_class = mocker.patch("devildex.core.AppPaths")
    mock_app_paths_instance = mock_app_paths_class.return_value
    mock_app_paths_instance.docsets_base_dir = tmp_path / "docsets"
    mock_app_paths_instance.database_path = db_url.replace("sqlite:///", "")
    mocker.patch.dict("os.environ", {"DEVILDEX_DEV_MODE": "0"})
    instance = DevilDexCore(database_url=db_url)
    return instance


def test_bootstrap_database_and_load_data(
    core: DevilDexCore,
    mock_installed_packages: list[PackageDetails],
    mocker: MockerFixture,
) -> None:
    """Verify that bootstrap_database_and_load_data correctly populates the DB."""
    mocker.patch(
        "devildex.core.DevilDexCore._bootstrap_database_read_db", return_value=[]
    )
    mock_ensure_pkg = mocker.patch(
        "devildex.core.database.ensure_package_entities_exist"
    )
    core.bootstrap_database_and_load_data(
        initial_package_source=mock_installed_packages, is_fallback_data=False
    )
    assert mock_ensure_pkg.call_count == len(mock_installed_packages)
    requests_call_args = mock_ensure_pkg.call_args_list[0].kwargs
    assert requests_call_args["package_name"] == "requests"
    assert requests_call_args["package_version"] == "2.25.1"
    assert requests_call_args["summary"] == "N/A"


def test_set_active_project_success(core: DevilDexCore, mocker: MockerFixture) -> None:
    """Verify that a valid project can be set as active."""
    project_details = {
        "project_name": "TestProject",
        "project_path": "/path/to/project",
        "python_executable": "/path/to/python",
    }
    mock_db_manager = mocker.patch("devildex.core.database.DatabaseManager")
    mock_db_manager.get_project_details_by_name.return_value = project_details
    mock_parser = mocker.patch("devildex.core.registered_project_parser")
    result = core.set_active_project("TestProject")
    assert result is True
    assert core.registered_project_name == "TestProject"
    assert core.registered_project_path == "/path/to/project"
    mock_db_manager.get_project_details_by_name.assert_called_once_with("TestProject")
    mock_parser.save_active_registered_project.assert_called_once_with(project_details)


def test_set_active_project_not_found_clears_state(
    core: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify behavior when setting a project that is not in the database."""
    mock_db_manager = mocker.patch("devildex.core.database.DatabaseManager")
    mock_db_manager.get_project_details_by_name.return_value = None
    mock_parser = mocker.patch("devildex.core.registered_project_parser")
    core.registered_project_name = "OldProject"
    result = core.set_active_project("NonExistentProject")
    assert result is False
    assert core.registered_project_name is None
    mock_parser.clear_active_registered_project.assert_called_once()


def test_set_active_project_to_none_for_global_view(
    core: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify that setting the active project to None clears state for global view."""
    mock_parser = mocker.patch("devildex.core.registered_project_parser")
    core.registered_project_name = "SomeProject"
    result = core.set_active_project(None)
    assert result is True
    assert core.registered_project_name is None
    mock_parser.clear_active_registered_project.assert_called_once()


def test_delete_docset_build_success_and_removes_empty_parent(
    core: DevilDexCore, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verify successful deletion of a docset build and its now-empty parent."""
    mock_rmtree = mocker.patch("shutil.rmtree")
    docset_version_path = tmp_path / "requests" / "2.25.1"
    docset_version_path.mkdir(parents=True)
    mocker.patch("pathlib.Path.iterdir", return_value=iter([]))
    success, msg = core.delete_docset_build(str(docset_version_path))
    assert success is True
    assert "Successfully deleted" in msg
    assert mock_rmtree.call_count == EXPECTED_RMTEE_CALL_COUNT
    mock_rmtree.assert_any_call(docset_version_path)
    mock_rmtree.assert_any_call(docset_version_path.parent)


def test_delete_docset_build_path_not_exist(core: DevilDexCore, tmp_path: Path) -> None:
    """Verify deletion fails if the target path does not exist."""
    non_existent_path = tmp_path / "non" / "existent" / "path"
    success, msg = core.delete_docset_build(str(non_existent_path))
    assert success is False
    assert "does not exist" in msg


def test_delete_docset_build_os_error(
    core: DevilDexCore, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verify deletion handles OSError gracefully."""
    mock_rmtree = mocker.patch(
        "shutil.rmtree", side_effect=OSError("Permission denied")
    )
    docset_version_path = tmp_path / "some_docset" / "1.0"
    docset_version_path.mkdir(parents=True)
    success, msg = core.delete_docset_build(str(docset_version_path))
    assert success is False
    assert "Permission denied" in msg
    mock_rmtree.assert_called_once_with(docset_version_path)


"""Tests for the DevilDexCore class."""


def test_generate_docset_success(core_with_db: DevilDexCore, mocker: MockerFixture) -> None:
    """Verify successful docset generation path."""
    mock_orchestrator_class = mocker.patch("devildex.core.Orchestrator")
    mock_orchestrator_instance = mock_orchestrator_class.return_value
    mock_orchestrator_instance.get_detected_doc_type.return_value = "pydoctor"
    mock_orchestrator_instance.grab_build_doc.return_value = "/path/to/generated/docset"
    package_data = {"name": "requests", "version": "2.25.1", "project_urls": {}}

    # Mock the threading.Thread to prevent actual thread creation and execution
    mock_thread_class = mocker.patch("devildex.core.threading.Thread")
    mock_thread_instance = mock_thread_class.return_value
    mock_thread_instance.start.return_value = None  # Ensure start does nothing

    task_id = core_with_db.generate_docset(package_data, force=True)

    # Manually call the target function to simulate thread execution
    # This ensures the _tasks dictionary is updated as if the thread ran
    core_with_db._run_generation_task(task_id, package_data, force=True)

    task_status = core_with_db.get_task_status(task_id)
    success, msg = task_status["result"]

    assert success is True
    assert msg == "/path/to/generated/docset"
    mock_orchestrator_class.assert_called_once()
    mock_orchestrator_instance.start_scan.assert_called_once()
    mock_orchestrator_instance.grab_build_doc.assert_called_once()


def test_generate_docset_unknown_type_failure(
    core_with_db: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify failure when the orchestrator cannot determine the doc type."""
    mock_orchestrator_class = mocker.patch("devildex.core.Orchestrator")
    mock_orchestrator_instance = mock_orchestrator_class.return_value
    mock_orchestrator_instance.get_detected_doc_type.return_value = "unknown"
    mock_orchestrator_instance.get_last_operation_result.return_value = (
        "No config file found"
    )

    package_data = {"name": "requests", "version": "2.25.1"}

    # Mock the threading.Thread to prevent actual thread creation and execution
    mock_thread_class = mocker.patch("devildex.core.threading.Thread")
    mock_thread_instance = mock_thread_class.return_value
    mock_thread_instance.start.return_value = None  # Ensure start does nothing

    task_id = core_with_db.generate_docset(package_data, force=True)

    # Manually call the target function to simulate thread execution
    core_with_db._run_generation_task(task_id, package_data, force=True)

    task_status = core_with_db.get_task_status(task_id)
    success, msg = task_status["result"]

    assert success is False
    assert "unable to determine" in msg
    assert "No config file found" in msg


def test_generate_docset_build_failure(
    core_with_db: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify failure when the build process itself fails."""
    mock_orchestrator_class = mocker.patch("devildex.core.Orchestrator")
    mock_orchestrator_instance = mock_orchestrator_class.return_value
    mock_orchestrator_instance.get_detected_doc_type.return_value = "pydoctor"
    mock_orchestrator_instance.grab_build_doc.return_value = False
    mock_orchestrator_instance.get_last_operation_result.return_value = (
        "pydoctor command failed"
    )

    package_data = {"name": "requests", "version": "2.25.1"}

    # Mock the threading.Thread to prevent actual thread creation and execution
    mock_thread_class = mocker.patch("devildex.core.threading.Thread")
    mock_thread_instance = mock_thread_class.return_value
    mock_thread_instance.start.return_value = None  # Ensure start does nothing

    task_id = core_with_db.generate_docset(package_data, force=True)

    # Manually call the target function to simulate thread execution
    core_with_db._run_generation_task(task_id, package_data, force=True)

    task_status = core_with_db.get_task_status(task_id)
    success, msg = task_status["result"]

    assert success is False
    assert "Failure nella generation" in msg
    assert "pydoctor command failed" in msg


def test_generate_docset_missing_input_data(
    core_with_db: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify early exit if package name or version is missing."""
    package_data = {"name": "requests"}

    # Mock search_for_docset to ensure no existing docsets are found
    mocker.patch("devildex.core.DevilDexCore.search_for_docset", return_value=[])

    # Mock the threading.Thread to prevent actual thread creation and execution
    mock_thread_class = mocker.patch("devildex.core.threading.Thread")
    mock_thread_instance = mock_thread_class.return_value
    mock_thread_instance.start.return_value = None  # Ensure start does nothing

    task_id = core_with_db.generate_docset(package_data)

    # Manually call the target function to simulate thread execution
    core_with_db._run_generation_task(task_id, package_data, force=False)

    task_status = core_with_db.get_task_status(task_id)
    success, msg = task_status["result"]

    assert success is False
    assert "missing package name or version" in msg


def test_scan_project_with_explicit_dependencies(
    core: DevilDexCore,
    mock_installed_packages: list[PackageDetails],
    mocker: MockerFixture,
) -> None:
    """Verify that scan_project filters packages based on explicit dependencies."""
    core.registered_project_name = "TestProject"
    core.registered_project_python_executable = "/path/to/python"
    mocker.patch(
        "devildex.core.get_explicit_dependencies_from_project_config",
        return_value={"requests", "numpy"},
    )
    mock_scanner = mocker.patch("devildex.core.ExternalVenvScanner").return_value
    mock_scanner.scan_packages.return_value = mock_installed_packages
    result = core.scan_project()
    assert result is not None
    assert len(result) == EXPECTED_SCANNED_PACKAGES_EXPLICIT
    package_names = {pkg.name for pkg in result}
    assert package_names == {"requests", "numpy"}


def test_scan_project_no_explicit_dependencies(
    core: DevilDexCore,
    mock_installed_packages: list[PackageDetails],
    mocker: MockerFixture,
) -> None:
    """Verify that scan_project returns all packages when no explicit deps are found."""
    core.registered_project_name = "TestProject"
    core.registered_project_python_executable = "/path/to/python"
    mocker.patch(
        "devildex.core.get_explicit_dependencies_from_project_config",
        return_value=set(),
    )
    mock_scanner = mocker.patch("devildex.core.ExternalVenvScanner").return_value
    mock_scanner.scan_packages.return_value = mock_installed_packages
    result = core.scan_project()
    assert result is not None
    assert len(result) == EXPECTED_SCANNED_PACKAGES_NO_EXPLICIT


def test_scan_project_no_project_active(core: DevilDexCore) -> None:
    """Verify that scan_project returns None when no project is active."""
    core.registered_project_name = None
    result = core.scan_project()
    assert result is None


def test_bootstrap_database_and_load_data_fallback(
    core: DevilDexCore,
    mock_installed_packages: list[PackageDetails],
    mocker: MockerFixture,
) -> None:
    """Verify that bootstrap_database_and_load_data handles fallback data correctly."""
    mocker.patch(
        "devildex.core.DevilDexCore._bootstrap_database_read_db", return_value=[]
    )
    mock_ensure_pkg = mocker.patch(
        "devildex.core.database.ensure_package_entities_exist"
    )
    core.bootstrap_database_and_load_data(
        initial_package_source=mock_installed_packages, is_fallback_data=True
    )
    requests_call_args = mock_ensure_pkg.call_args_list[0].kwargs
    assert "project_name" not in requests_call_args


def test_bootstrap_database_and_load_data_missing_pkg_data(
    core: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify that packages with missing name or version are skipped."""
    mocker.patch(
        "devildex.core.DevilDexCore._bootstrap_database_read_db", return_value=[]
    )
    mock_ensure_pkg = mocker.patch(
        "devildex.core.database.ensure_package_entities_exist"
    )
    packages = [PackageDetails(name="requests", version=None, project_urls={})]
    core.bootstrap_database_and_load_data(
        initial_package_source=packages, is_fallback_data=False
    )

    mock_ensure_pkg.assert_not_called()


def test_list_package_dirs_no_base_dir(core: DevilDexCore, tmp_path: Path) -> None:
    """Verify list_package_dirs returns empty list if base directory doesn't exist."""
    core.docset_base_output_path = tmp_path / "non_existent_dir"
    result = core.list_package_dirs()
    assert result == []


def test_dev_mode_paths(mocker: MockerFixture, tmp_path: Path) -> None:
    """Verify that DEV_MODE uses the correct paths."""
    mocker.patch.dict("os.environ", {"DEVILDEX_DEV_MODE": "1"})
    mock_app_paths_class = mocker.patch("devildex.core.AppPaths")
    mock_app_paths_instance = mock_app_paths_class.return_value
    mock_app_paths_instance.docsets_base_dir = tmp_path / "docsets"
    mock_app_paths_instance.database_path = tmp_path / "devildex_test.db"
    core = DevilDexCore()
    assert core.docset_base_output_path == mock_app_paths_instance.docsets_base_dir