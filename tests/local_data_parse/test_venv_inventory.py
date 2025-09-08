"""Tests for the venv_inventory module."""

import logging
from unittest.mock import MagicMock, patch

from devildex.local_data_parse.venv_inventory import (
    get_installed_packages_with_project_urls,
)
from devildex.database.models import PackageDetails


def create_mock_distribution(
    name: str, version: str, project_urls_metadata: list[str] | None
) -> MagicMock:
    """Create a mock distribution object for testing."""
    mock_dist = MagicMock()
    mock_dist.name = name
    mock_dist.version = version
    # The metadata object itself needs to be a mock to have the .get_all method
    mock_dist.metadata = MagicMock()
    mock_dist.metadata.get_all.return_value = project_urls_metadata
    return mock_dist


@patch("devildex.local_data_parse.venv_inventory.importlib.metadata.distributions")
def test_get_installed_packages_success(mock_distributions: MagicMock) -> None:
    """Verify installed packages are correctly identified and project URLs parsed."""
    # Arrange
    mock_distributions.return_value = [
        create_mock_distribution(
            name="requests",
            version="2.25.1",
            project_urls_metadata=[
                "Homepage, https://requests.readthedocs.io",
                "Source, https://github.com/psf/requests",
            ],
        ),
        create_mock_distribution(
            name="numpy",
            version="1.21.0",
            project_urls_metadata=None,  # Test case with no URLs
        ),
    ]

    # Act
    packages = get_installed_packages_with_project_urls()

    # Assert
    assert len(packages) == 2
    assert all(isinstance(p, PackageDetails) for p in packages)

    requests_pkg = next(p for p in packages if p.name == "requests")
    assert requests_pkg.version == "2.25.1"
    assert requests_pkg.project_urls == {
        "Homepage": "https://requests.readthedocs.io",
        "Source": "https://github.com/psf/requests",
    }

    numpy_pkg = next(p for p in packages if p.name == "numpy")
    assert numpy_pkg.version == "1.21.0"
    assert numpy_pkg.project_urls == {}


@patch("devildex.local_data_parse.venv_inventory.importlib.metadata.distributions")
def test_get_installed_packages_with_explicit_filter(
    mock_distributions: MagicMock,
) -> None:
    """Verify that providing an 'explicit' set correctly filters the packages."""
    # Arrange
    mock_distributions.return_value = [
        create_mock_distribution("requests", "2.25.1", []),
        create_mock_distribution("numpy", "1.21.0", []),
        create_mock_distribution("pytest", "7.0.0", []),
    ]
    explicit_set = {"requests", "pytest"}

    # Act
    packages = get_installed_packages_with_project_urls(explicit=explicit_set)

    # Assert
    assert len(packages) == 2
    package_names = {p.name for p in packages}
    assert package_names == {"requests", "pytest"}


@patch("devildex.local_data_parse.venv_inventory.importlib.metadata.distributions")
def test_handle_project_urls_malformed_entry(
    mock_distributions: MagicMock, caplog
) -> None:
    """Verify that a malformed Project-URL entry is skipped and a warning is logged."""
    # Arrange
    mock_distributions.return_value = [
        create_mock_distribution(
            name="bad-package",
            version="1.0.0",
            project_urls_metadata=[
                "Homepage, https://good.url",
                "JustOnePart",  # Malformed entry
            ],
        )
    ]

    # Act
    with caplog.at_level(logging.WARNING):
        packages = get_installed_packages_with_project_urls()

    # Assert
    assert len(packages) == 1
    bad_pkg = packages[0]
    assert bad_pkg.name == "bad-package"
    # The malformed entry should be ignored, but the good one should be present
    assert bad_pkg.project_urls == {"Homepage": "https://good.url"}

    # Check that the warning was logged
    assert "ATTENTION: impossible to analyze the project-url item" in caplog.text
    assert "bad-package" in caplog.text
    assert "'JustOnePart'" in caplog.text


@patch("devildex.local_data_parse.venv_inventory.importlib.metadata.distributions")
def test_get_installed_packages_no_packages_found(
    mock_distributions: MagicMock,
) -> None:
    """Verify that an empty list is returned when no packages are found."""
    # Arrange
    mock_distributions.return_value = []

    # Act
    packages = get_installed_packages_with_project_urls()

    # Assert
    assert packages == []
