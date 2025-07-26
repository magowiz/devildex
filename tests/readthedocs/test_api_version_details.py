"""Tests for the version detail fetching logic in the ReadTheDocs API client."""

import json

import requests
from pytest_mock import MockerFixture

from devildex.readthedocs.readthedocs_api import _fetch_version_details


class MockResponse:
    """A mock class to simulate requests.Response for testing."""

    def __init__(self, json_data=None, text_data="", status_code=200):
        """Initialize the mock response."""
        self._json_data = json_data
        self._text_data = text_data
        self.status_code = status_code

    def json(self):
        """Mock the json() method."""
        if self._json_data is not None:
            return self._json_data
        # Simulate the error caught in the source code
        raise json.JSONDecodeError("Expecting value", self._text_data, 0)

    def raise_for_status(self):
        """Mock the raise_for_status() method."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"Error {self.status_code}")


def test_fetch_version_details_success(mocker: MockerFixture):
    """Verify it correctly returns data on a successful API call."""
    # Arrange
    project_slug = "my-project"
    version_slug = "stable"
    mock_api_response = {
        "id": 123,
        "slug": "stable",
        "downloads": {"pdf": "http://example.com/doc.pdf"},
    }
    mock_get = mocker.patch(
        "requests.get",
        return_value=MockResponse(json_data=mock_api_response, status_code=200),
    )

    # Act
    details = _fetch_version_details(project_slug, version_slug)

    # Assert
    assert details is not None
    assert details["slug"] == "stable"
    assert "pdf" in details["downloads"]
    mock_get.assert_called_once()
    # Verify the correct parameters were passed to the API call
    called_args, called_kwargs = mock_get.call_args
    assert f"/versions/{version_slug}/" in called_args[0]
    assert called_kwargs["params"] == {"project__slug": project_slug}


def test_fetch_version_details_handles_http_error(mocker: MockerFixture):
    """Verify it returns None on an HTTP error (e.g., 404 Not Found)."""
    # Arrange
    mocker.patch("requests.get", return_value=MockResponse(status_code=404))

    # Act & Assert
    assert _fetch_version_details("my-project", "nonexistent-version") is None


def test_fetch_version_details_handles_network_error(mocker: MockerFixture):
    """Verify it returns None on a generic network request exception."""
    # Arrange
    mocker.patch("requests.get", side_effect=requests.exceptions.RequestException)

    # Act & Assert
    assert _fetch_version_details("my-project", "stable") is None


def test_fetch_version_details_handles_json_decode_error(mocker: MockerFixture):
    """Verify it returns None if the API returns invalid JSON."""
    # Arrange
    mocker.patch(
        "requests.get", return_value=MockResponse(text_data="<error>not json</error>")
    )

    # Act & Assert
    assert _fetch_version_details("my-project", "stable") is None
