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
    """Provides a DevilDexCore instance with its paths mocked to use a temporary directory.
    This leaves the production DevilDexCore.__init__ unchanged.
    """
    # FIX: Non modifichiamo il costruttore di DevilDexCore.
    # Invece, intercettiamo (mock) la classe AppPaths che usa internamente.
    mock_app_paths_class = mocker.patch("devildex.core.AppPaths")
    mock_app_paths_instance = mock_app_paths_class.return_value

    # Configuriamo l'istanza del mock per usare i nostri percorsi temporanei.
    # Quando DevilDexCore farà `self.app_paths = AppPaths()`, riceverà questo mock.
    mock_app_paths_instance.docsets_base_dir = tmp_path / "docsets"
    mock_app_paths_instance.database_path = tmp_path / "devildex_test.db"

    # Assicuriamoci che l'ambiente non sia in modalità DEV per il test,
    # così userà sicuramente i percorsi di AppPaths che abbiamo mockato.
    mocker.patch.dict("os.environ", {"DEVILDEX_DEV_MODE": "0"})

    # Ora possiamo creare l'istanza di DevilDexCore in modo sicuro.
    # Il suo __init__ userà i percorsi che abbiamo appena definito nel mock.
    instance = DevilDexCore()
    return instance


def test_bootstrap_database_and_load_data(
    core: DevilDexCore,
    mock_installed_packages: list[PackageDetails],
    mocker: MockerFixture,
):
    """Verify that bootstrap_database_and_load_data correctly populates the DB
    and returns structured data for the grid.
    """
    # Arrange
    # Mock della funzione che legge dal DB per isolare il test alla sola scrittura
    mocker.patch(
        "devildex.core.DevilDexCore._bootstrap_database_read_db", return_value=[]
    )
    mock_ensure_pkg = mocker.patch("devildex.database.ensure_package_entities_exist")

    # Act
    core.bootstrap_database_and_load_data(
        initial_package_source=mock_installed_packages, is_fallback_data=False
    )

    # Assert
    # Verifichiamo che abbia provato a scrivere nel DB per ogni pacchetto
    assert mock_ensure_pkg.call_count == len(mock_installed_packages)

    # Verifichiamo i dati passati per uno dei pacchetti
    requests_call_args = mock_ensure_pkg.call_args_list[0].kwargs
    assert requests_call_args["package_name"] == "requests"
    assert requests_call_args["package_version"] == "2.25.1"
    # Since PackageDetails doesn't have a summary, the core logic correctly
    # falls back to "N/A". The test must reflect this actual behavior.
    assert requests_call_args["summary"] == "N/A"
