"""Tests for the download URL extraction logic in the ReadTheDocs API client."""

import logging

import pytest

from devildex.readthedocs.readthedocs_api import _get_download_url


@pytest.fixture
def sample_version_details() -> dict:
    """Provide a sample version details dictionary with download URLs."""
    return {
        "slug": "stable",
        "downloads": {
            "htmlzip": "https://example.com/docs/project-stable.zip",
            "pdf": "https://example.com/docs/project-stable.pdf",
            "epub": "//example.com/docs/project-stable.epub",
        },
    }


def test_get_download_url_success(sample_version_details: dict) -> None:
    """Verify it correctly extracts the URL for a given format."""
    url = _get_download_url(sample_version_details, "htmlzip")
    assert url == "https://example.com/docs/project-stable.zip"


def test_get_download_url_handles_protocol_relative_url(
    sample_version_details: dict,
) -> None:
    """Verify it correctly prepends 'https:' to protocol-relative URLs."""
    url = _get_download_url(sample_version_details, "epub")
    assert url == "https://example.com/docs/project-stable.epub"


def test_get_download_url_returns_none_for_missing_format(
    sample_version_details: dict,
) -> None:
    """Verify it returns None when the requested format is not available."""
    url = _get_download_url(sample_version_details, "nonexistent_format")
    assert url is None


def test_get_download_url_returns_none_for_missing_downloads_key() -> None:
    """Verify it returns None if the 'downloads' key is missing from the details."""
    details_without_downloads = {"slug": "stable"}
    url = _get_download_url(details_without_downloads, "htmlzip")
    assert url is None


def test_get_download_url_returns_none_for_empty_or_none_details() -> None:
    """Verify it returns None if the version_details dictionary is empty or None."""
    assert _get_download_url({}, "htmlzip") is None
    # The type hint is `dict`, but let's be robust and test for None as well
    assert _get_download_url(None, "htmlzip") is None


def test_get_download_url_handles_non_standard_extension_url(caplog) -> None:
    """Verify it logs a warning for URLs without a standard archive extension."""
    details = {
        "slug": "stable",
        "downloads": {"htmlzip": "https://example.com/download/latest"},
    }
    with caplog.at_level(logging.WARNING):
        url = _get_download_url(details, "htmlzip")
        assert url == "https://example.com/download/latest"
        assert "may not be a direct link" in caplog.text
