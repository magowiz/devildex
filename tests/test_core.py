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
