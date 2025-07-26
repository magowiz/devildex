"""Tests for the version fetching logic in the ReadTheDocs API client."""

import json

import requests
from pytest_mock import MockerFixture

from devildex.readthedocs.readthedocs_api import (
    _fetch_available_versions,
)


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


def test_fetch_available_versions_single_page(mocker: MockerFixture):
    """Verify it correctly fetches versions from a single API page."""
    # Arrange
    mock_api_response = {
        "count": 2,
        "next": None,
        "results": [
            {"slug": "stable", "active": True, "built": True},
            {"slug": "latest", "active": True, "built": True},
        ],
    }
    mock_get = mocker.patch(
        "requests.get",
        return_value=MockResponse(json_data=mock_api_response, status_code=200),
    )

    # Act
    versions = _fetch_available_versions("my-project")

    # Assert
    assert versions is not None
    assert len(versions) == 2
    assert versions[0]["slug"] == "stable"
    mock_get.assert_called_once()


def test_fetch_available_versions_with_pagination(mocker: MockerFixture):
    """Verify it correctly handles API pagination across multiple pages."""
    # Arrange
    page1_response = {
        "count": 2,
        "next": "http://api.example.com/page2",
        "results": [{"slug": "v2.0"}],
    }
    page2_response = {"count": 2, "next": None, "results": [{"slug": "v1.0"}]}
    mock_get = mocker.patch(
        "requests.get",
        side_effect=[
            MockResponse(json_data=page1_response, status_code=200),
            MockResponse(json_data=page2_response, status_code=200),
        ],
    )

    # Act
    versions = _fetch_available_versions("my-project")

    # Assert
    assert versions is not None
    assert len(versions) == 2
    assert [v["slug"] for v in versions] == ["v2.0", "v1.0"]
    assert mock_get.call_count == 2


def test_fetch_available_versions_handles_network_error(mocker: MockerFixture):
    """Verify it returns None on a network error like a timeout or DNS failure."""
    mocker.patch("requests.get", side_effect=requests.exceptions.RequestException)
    assert _fetch_available_versions("my-project") is None


def test_fetch_available_versions_handles_json_decode_error(mocker: MockerFixture):
    """Verify it returns None when the API response is not valid JSON."""
    mocker.patch("requests.get", return_value=MockResponse(text_data="invalid json"))
    assert _fetch_available_versions("my-project") is None
