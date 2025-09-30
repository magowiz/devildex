"""Tests for the docset scanning logic within the DevilDexApp class."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from devildex.constants import AVAILABLE_BTN_LABEL, NOT_AVAILABLE_BTN_LABEL
from devildex.main import DevilDexApp


@pytest.fixture
def app(mocker: MockerFixture, tmp_path: Path) -> DevilDexApp:
    """Provide a DevilDexApp instance for testing without a running event loop."""
    mocker.patch("wx.App.__init__", return_value=None)
    mock_core = mocker.MagicMock(name="DevilDexCore")
    mock_core.docset_base_output_path = tmp_path
    app_instance = DevilDexApp(core=mock_core)
    return app_instance


def test_perform_startup_docset_scan(
    app: DevilDexApp, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verify that _perform_startup_docset_scan correctly updates package data.

    based on the directories found on the filesystem.
    """
    app.current_grid_source_data = [
        {"name": "black", "version": "24.4.2", "docset_status": "Initial"},
        {"name": "flask", "version": "3.0.3", "docset_status": "Initial"},
        {"name": "requests", "version": "2.31.0", "docset_status": "Initial"},
        {
            "name": "old-package",
            "version": "1.0.0",
            "docset_status": AVAILABLE_BTN_LABEL,
            "docset_path": "/stale/path",
        },
    ]
    (tmp_path / "black" / "24.4.2").mkdir(parents=True)
    (tmp_path / "flask" / "main").mkdir(parents=True)
    app.core.list_package_dirs.return_value = ["black", "flask"]
    app._perform_startup_docset_scan()
    black_pkg = next(p for p in app.current_grid_source_data if p["name"] == "black")
    flask_pkg = next(p for p in app.current_grid_source_data if p["name"] == "flask")
    requests_pkg = next(
        p for p in app.current_grid_source_data if p["name"] == "requests"
    )
    old_pkg = next(
        p for p in app.current_grid_source_data if p["name"] == "old-package"
    )
    assert black_pkg["docset_status"] == AVAILABLE_BTN_LABEL
    assert "docset_path" in black_pkg
    assert black_pkg["docset_path"] == str((tmp_path / "black" / "24.4.2").resolve())
    assert flask_pkg["docset_status"] == AVAILABLE_BTN_LABEL
    assert "docset_path" in flask_pkg
    assert flask_pkg["docset_path"] == str((tmp_path / "flask" / "main").resolve())
    assert requests_pkg["docset_status"] == NOT_AVAILABLE_BTN_LABEL
    assert "docset_path" not in requests_pkg
    assert old_pkg["docset_status"] == NOT_AVAILABLE_BTN_LABEL
    assert "docset_path" not in old_pkg
