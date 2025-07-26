"""Tests for the docset scanning logic within the DevilDexApp class."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.constants import AVAILABLE_BTN_LABEL, NOT_AVAILABLE_BTN_LABEL
from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture, tmp_path: Path) -> DevilDexApp:
    """Provide a DevilDexApp instance for testing without a running event loop."""
    # Prevent the real wx.App from initializing
    mocker.patch("wx.App.__init__", return_value=None)

    # Mock the core dependency and set the docset path
    mock_core = mocker.MagicMock(name="DevilDexCore")
    mock_core.docset_base_output_path = tmp_path

    # Create the app instance with the mocked core
    app_instance = DevilDexApp(core=mock_core)

    return app_instance


def test_perform_startup_docset_scan(
    app: DevilDexApp, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verify that _perform_startup_docset_scan correctly updates package data.

    based on the directories found on the filesystem.
    """
    # Arrange
    # 1. Define the initial state of the packages in the app
    app.current_grid_source_data = [
        # Case 1: Docset exists in a versioned folder
        {"name": "black", "version": "24.4.2", "docset_status": "Initial"},
        # Case 2: Docset exists in a 'main' folder
        {"name": "flask", "version": "3.0.3", "docset_status": "Initial"},
        # Case 3: No docset folder exists for this package
        {"name": "requests", "version": "2.31.0", "docset_status": "Initial"},
        # Case 4: Docset was previously available but now is gone
        {
            "name": "old-package",
            "version": "1.0.0",
            "docset_status": AVAILABLE_BTN_LABEL,
            "docset_path": "/stale/path",
        },
    ]

    # 2. Simulate the filesystem structure
    # For 'black'
    (tmp_path / "black" / "24.4.2").mkdir(parents=True)
    # For 'flask'
    (tmp_path / "flask" / "main").mkdir(parents=True)
    # 'requests' and 'old-package' have no corresponding folders

    # 3. Mock the core's list_package_dirs to return the top-level dirs we created
    app.core.list_package_dirs.return_value = ["black", "flask"]

    # Act
    app._perform_startup_docset_scan()

    # Assert
    # Check the results for each package
    black_pkg = next(p for p in app.current_grid_source_data if p["name"] == "black")
    flask_pkg = next(p for p in app.current_grid_source_data if p["name"] == "flask")
    requests_pkg = next(
        p for p in app.current_grid_source_data if p["name"] == "requests"
    )
    old_pkg = next(
        p for p in app.current_grid_source_data if p["name"] == "old-package"
    )

    # Case 1: black should be available
    assert black_pkg["docset_status"] == AVAILABLE_BTN_LABEL
    assert "docset_path" in black_pkg
    assert black_pkg["docset_path"] == str((tmp_path / "black" / "24.4.2").resolve())

    # Case 2: flask should be available
    assert flask_pkg["docset_status"] == AVAILABLE_BTN_LABEL
    assert "docset_path" in flask_pkg
    assert flask_pkg["docset_path"] == str((tmp_path / "flask" / "main").resolve())

    # Case 3: requests should be not available
    assert requests_pkg["docset_status"] == NOT_AVAILABLE_BTN_LABEL
    assert "docset_path" not in requests_pkg

    # Case 4: old-package should now be not available
    assert old_pkg["docset_status"] == NOT_AVAILABLE_BTN_LABEL
    assert "docset_path" not in old_pkg
