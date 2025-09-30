"""Tests for the external_venv_scanner module."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from devildex.database.models import PackageDetails
from devildex.local_data_parse.external_venv_scanner import ExternalVenvScanner


@pytest.fixture
def mock_python_executable(tmp_path: Path) -> Path:
    """Create a mock python executable file."""
    py_exec = tmp_path / "bin" / "python"
    py_exec.parent.mkdir()
    py_exec.touch()
    return py_exec


def test_scan_packages_success(mock_python_executable: Path, mocker: MagicMock) -> None:
    """Verify a successful package scan returns a list of PackageDetails."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
    mock_temp_file = mocker.patch("tempfile.NamedTemporaryFile")
    temp_file_path = mock_python_executable.parent.parent / "scan.json"
    mock_file_handle = MagicMock()
    mock_file_handle.__enter__.return_value.name = str(temp_file_path)
    mock_temp_file.return_value = mock_file_handle
    expected_packages_data = [
        {
            "name": "requests",
            "version": "2.25.1",
            "summary": "HTTP for Humans.",
            "project_urls": {"Homepage": "https://requests.readthedocs.io"},
        }
    ]
    temp_file_path.write_text(json.dumps(expected_packages_data))
    scanner = ExternalVenvScanner(python_executable_path=str(mock_python_executable))
    result = scanner.scan_packages()
    assert result is not None
    assert len(result) == 1
    assert isinstance(result[0], PackageDetails)
    assert result[0].name == "requests"
    assert result[0].version == "2.25.1"
    assert result[0].project_urls["Homepage"] == "https://requests.readthedocs.io"
    assert not temp_file_path.exists()


def test_scan_packages_script_fails(
    mock_python_executable: Path, mocker: MagicMock
) -> None:
    """Verify that a non-zero return code from the script results in None."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=1, stderr="Script error"
    )
    mocker.patch("tempfile.NamedTemporaryFile")
    scanner = ExternalVenvScanner(python_executable_path=str(mock_python_executable))
    result = scanner.scan_packages()
    assert result is None


def test_scan_packages_invalid_python_path() -> None:
    """Verify that an invalid python executable path returns None."""
    invalid_path = "/path/to/non/existent/python"
    scanner = ExternalVenvScanner(python_executable_path=invalid_path)
    result = scanner.scan_packages()
    assert result is None


def test_scan_packages_empty_json_output(
    mock_python_executable: Path, mocker: MagicMock
) -> None:
    """Verify that an empty JSON file (e.g., empty venv) returns an empty list."""
    mocker.patch("subprocess.run").return_value = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    mock_temp_file = mocker.patch("tempfile.NamedTemporaryFile")
    temp_file_path = mock_python_executable.parent.parent / "empty_scan.json"
    mock_file_handle = MagicMock()
    mock_file_handle.__enter__.return_value.name = str(temp_file_path)
    mock_temp_file.return_value = mock_file_handle
    temp_file_path.touch()
    scanner = ExternalVenvScanner(python_executable_path=str(mock_python_executable))
    result = scanner.scan_packages()
    assert result == []
