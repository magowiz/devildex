"""Tests for the local filename determination logic in the ReadTheDocs API client."""

import pytest

from devildex.readthedocs.readthedocs_api import (
    _determine_local_filename,
)

test_cases = [
    (
        "requests",
        "v2.31.0",
        "https://media.readthedocs.org/htmlzip/requests/v2.31.0/requests.zip",
        "htmlzip",
        "requests.zip",
    ),
    (
        "django",
        "4.2",
        "https://media.readthedocs.org/pdf/django/4.2/django.pdf",
        "pdf",
        "django.pdf",
    ),
    (
        "my-project",
        "latest",
        "https://example.com/download/latest/",
        "htmlzip",
        "my-project-latest.zip",
    ),
    (
        "some-project",
        "feature-branch",
        "https://example.com/downloads/this-is-a-very-very-very-long-filename-that-exceeds-the-maximum-allowed-length.zip",
        "htmlzip",
        "some-project-feature-branch.zip",
    ),
    # Case: URL has query parameters that should be ignored
    (
        "another-project",
        "stable",
        "https://example.com/files/another-project.zip?token=12345&expires=tomorrow",
        "htmlzip",
        "another-project.zip",
    ),
    # Case: download_format is 'htmlzip', should result in '.zip' extension
    (
        "special-case",
        "v1",
        "https://example.com/download/1",
        "htmlzip",
        "special-case-v1.zip",
    ),
    (
        "book-project",
        "final",
        "https://example.com/download/book",
        "epub",
        "book-project-final.epub",
    ),
]


@pytest.mark.parametrize(
    "project_slug, version_slug, download_url, download_format, expected_filename",
    test_cases,
)
def test_determine_local_filename(
    project_slug: str,
    version_slug: str,
    download_url: str,
    download_format,
    expected_filename: str,
) -> None:
    """Verify local filename is determined correctly across various scenarios."""
    result = _determine_local_filename(
        project_slug, version_slug, download_url, download_format
    )
    assert result == expected_filename
