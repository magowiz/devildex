"""Tests for the DevilDexCore class."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.core import DevilDexCore
from devildex.models import PackageDetails


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


def test_bootstrap_database_and_load_data(
    core: DevilDexCore,
    mock_installed_packages: list[PackageDetails],
    mocker: MockerFixture,
) -> None:
    """Verify that bootstrap_database_and_load_data correctly populates the DB."""
    # Arrange
    mocker.patch(
        "devildex.core.DevilDexCore._bootstrap_database_read_db", return_value=[]
    )
    mock_ensure_pkg = mocker.patch("devildex.database.ensure_package_entities_exist")

    # Act
    core.bootstrap_database_and_load_data(
        initial_package_source=mock_installed_packages, is_fallback_data=False
    )

    # Assert
    assert mock_ensure_pkg.call_count == len(mock_installed_packages)

    requests_call_args = mock_ensure_pkg.call_args_list[0].kwargs
    assert requests_call_args["package_name"] == "requests"
    assert requests_call_args["package_version"] == "2.25.1"
    assert requests_call_args["summary"] == "N/A"


def test_set_active_project_success(core: DevilDexCore, mocker: MockerFixture) -> None:
    """Verify that a valid project can be set as active."""
    # Arrange
    project_details = {
        "project_name": "TestProject",
        "project_path": "/path/to/project",
        "python_executable": "/path/to/python",
    }
    mock_db_manager = mocker.patch("devildex.core.database.DatabaseManager")
    mock_db_manager.get_project_details_by_name.return_value = project_details
    mock_parser = mocker.patch("devildex.core.registered_project_parser")

    # Act
    result = core.set_active_project("TestProject")

    # Assert
    assert result is True
    assert core.registered_project_name == "TestProject"
    assert core.registered_project_path == "/path/to/project"
    mock_db_manager.get_project_details_by_name.assert_called_once_with("TestProject")
    mock_parser.save_active_registered_project.assert_called_once_with(project_details)


def test_set_active_project_not_found_clears_state(
    core: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify behavior when setting a project that is not in the database."""
    # Arrange
    mock_db_manager = mocker.patch("devildex.core.database.DatabaseManager")
    mock_db_manager.get_project_details_by_name.return_value = None
    mock_parser = mocker.patch("devildex.core.registered_project_parser")
    core.registered_project_name = "OldProject"  # Set some initial state

    # Act
    result = core.set_active_project("NonExistentProject")

    # Assert
    assert result is False
    assert core.registered_project_name is None  # Should be cleared
    mock_parser.clear_active_registered_project.assert_called_once()


def test_set_active_project_to_none_for_global_view(
    core: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify that setting the active project to None clears state for global view."""
    # Arrange
    mock_parser = mocker.patch("devildex.core.registered_project_parser")
    core.registered_project_name = "SomeProject"

    # Act
    result = core.set_active_project(None)

    # Assert
    assert result is True
    assert core.registered_project_name is None
    mock_parser.clear_active_registered_project.assert_called_once()


def test_delete_docset_build_success_and_removes_empty_parent(
    core: DevilDexCore, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verify successful deletion of a docset build and its now-empty parent."""
    # Arrange
    mock_rmtree = mocker.patch("shutil.rmtree")
    docset_version_path = tmp_path / "requests" / "2.25.1"
    docset_version_path.mkdir(parents=True)

    # FIX: Patch the method on the 'pathlib.Path' class, not on a specific instance.
    # This is the standard and robust way to mock methods on built-in types.
    mocker.patch("pathlib.Path.iterdir", return_value=iter([]))

    # Act
    success, msg = core.delete_docset_build(str(docset_version_path))

    # Assert
    assert success is True
    assert "Successfully deleted" in msg
    assert mock_rmtree.call_count == 2
    mock_rmtree.assert_any_call(docset_version_path)
    mock_rmtree.assert_any_call(docset_version_path.parent)


def test_delete_docset_build_path_not_exist(core: DevilDexCore) -> None:
    """Verify deletion fails if the target path does not exist."""
    # Arrange
    non_existent_path = "/tmp/non/existent/path"

    # Act
    success, msg = core.delete_docset_build(non_existent_path)

    # Assert
    assert success is False
    assert "does not exist" in msg


def test_delete_docset_build_os_error(
    core: DevilDexCore, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verify deletion handles OSError gracefully."""
    # Arrange
    mock_rmtree = mocker.patch(
        "shutil.rmtree", side_effect=OSError("Permission denied")
    )
    docset_version_path = tmp_path / "some_docset" / "1.0"
    docset_version_path.mkdir(parents=True)

    # Act
    success, msg = core.delete_docset_build(str(docset_version_path))

    # Assert
    assert success is False
    assert "Permission denied" in msg
    mock_rmtree.assert_called_once_with(docset_version_path)


"""Tests for the DevilDexCore class."""





def test_generate_docset_success(core: DevilDexCore, mocker: MockerFixture) -> None:
    """Verify successful docset generation path."""
    # Arrange
    mock_orchestrator_class = mocker.patch("devildex.core.Orchestrator")
    mock_orchestrator_instance = mock_orchestrator_class.return_value
    mock_orchestrator_instance.get_detected_doc_type.return_value = "pydoctor"
    mock_orchestrator_instance.grab_build_doc.return_value = "/path/to/generated/docset"

    package_data = {"name": "requests", "version": "2.25.1", "project_urls": {}}

    # Act
    success, msg = core.generate_docset(package_data)

    # Assert
    assert success is True
    assert msg == "/path/to/generated/docset"
    mock_orchestrator_class.assert_called_once()
    mock_orchestrator_instance.start_scan.assert_called_once()
    mock_orchestrator_instance.grab_build_doc.assert_called_once()


def test_generate_docset_unknown_type_failure(
    core: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify failure when the orchestrator cannot determine the doc type."""
    # Arrange
    mock_orchestrator_class = mocker.patch("devildex.core.Orchestrator")
    mock_orchestrator_instance = mock_orchestrator_class.return_value
    mock_orchestrator_instance.get_detected_doc_type.return_value = "unknown"
    mock_orchestrator_instance.get_last_operation_result.return_value = (
        "No config file found"
    )

    package_data = {"name": "requests", "version": "2.25.1"}

    # Act
    success, msg = core.generate_docset(package_data)

    # Assert
    assert success is False
    assert "unable to determine" in msg
    assert "No config file found" in msg


def test_generate_docset_build_failure(
    core: DevilDexCore, mocker: MockerFixture
) -> None:
    """Verify failure when the build process itself fails."""
    # Arrange
    mock_orchestrator_class = mocker.patch("devildex.core.Orchestrator")
    mock_orchestrator_instance = mock_orchestrator_class.return_value
    mock_orchestrator_instance.get_detected_doc_type.return_value = "pydoctor"
    mock_orchestrator_instance.grab_build_doc.return_value = False
    mock_orchestrator_instance.get_last_operation_result.return_value = (
        "pydoctor command failed"
    )

    package_data = {"name": "requests", "version": "2.25.1"}

    # Act
    success, msg = core.generate_docset(package_data)

    # Assert
    assert success is False
    assert "Failure nella generation" in msg
    assert "pydoctor command failed" in msg


def test_generate_docset_missing_input_data(core: DevilDexCore) -> None:
    """Verify early exit if package name or version is missing."""
    # Arrange
    package_data = {"name": "requests"}  # Missing version

    # Act
    success, msg = core.generate_docset(package_data)

    # Assert
    assert success is False
    assert "missing package name or version" in msg
