"""Tests for the file download logic in the ReadTheDocs API client."""

from pathlib import Path

import requests
from pytest_mock import MockerFixture

from devildex.readthedocs.readthedocs_api import _download_file

# A small chunk of fake binary data to simulate a download
FAKE_FILE_CONTENT = b"some-binary-zip-content"


class MockStreamResponse:
    """A mock class to simulate a streaming requests.Response for testing."""

    def __init__(self, content, status_code=200):
        """Initialize the mock stream response."""
        self.status_code = status_code
        self._content_iterator = iter([content])

    def raise_for_status(self):
        """Mock raise_for_status to raise on bad status codes."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"Error {self.status_code}")

    def iter_content(self, chunk_size=8192):
        """Mock iter_content to return our fake content."""
        return self._content_iterator

    def __enter__(self):
        """Allow use in 'with' statements."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Handle exiting 'with' statements."""
        pass


def test_download_file_success(mocker: MockerFixture, tmp_path: Path):
    """Verify a file is successfully downloaded and written to disk."""
    # Arrange
    file_url = "https://example.com/file.zip"
    local_filepath = tmp_path / "downloaded.zip"

    # Mock the network request to return our fake streaming response
    mocker.patch(
        "requests.get",
        return_value=MockStreamResponse(content=FAKE_FILE_CONTENT),
    )

    # Mock the file system write operation
    mock_open = mocker.patch("builtins.open", mocker.mock_open())

    # Act
    result = _download_file(file_url, local_filepath)

    # Assert
    assert result is True
    mock_open.assert_called_once_with(local_filepath, "wb")
    mock_open().write.assert_called_once_with(FAKE_FILE_CONTENT)


def test_download_file_handles_network_error(mocker: MockerFixture, tmp_path: Path):
    """Verify it returns False and cleans up a partial file on a network error."""
    # Arrange
    file_url = "https://example.com/file.zip"
    local_filepath = tmp_path / "partial.zip"

    # Mock the network request to fail
    mocker.patch("requests.get", side_effect=requests.exceptions.RequestException)

    # Mock os.path.exists and os.remove to verify cleanup logic
    mocker.patch("os.path.exists", side_effect=[True, False])
    mock_remove = mocker.patch("os.remove")

    # Act
    result = _download_file(file_url, local_filepath)

    # Assert
    assert result is False
    mock_remove.assert_called_once_with(local_filepath)


def test_download_file_handles_os_error_on_write(mocker: MockerFixture, tmp_path: Path):
    """Verify it returns False and cleans up if writing to disk fails."""
    # Arrange
    file_url = "https://example.com/file.zip"
    local_filepath = tmp_path / "failed_write.zip"

    # Mock the network request to succeed
    mocker.patch(
        "requests.get",
        return_value=MockStreamResponse(content=FAKE_FILE_CONTENT),
    )

    # Mock `open` to raise an OSError, simulating a disk full error
    mocker.patch("builtins.open", side_effect=OSError("Disk full"))

    # Mock os.path.exists and os.remove to verify cleanup logic
    mocker.patch("os.path.exists", side_effect=[True, False])
    mock_remove = mocker.patch("os.remove")

    # Act
    result = _download_file(file_url, local_filepath)

    # Assert
    assert result is False
    mock_remove.assert_called_once_with(local_filepath)


def test_download_file_no_cleanup_if_file_not_created(
    mocker: MockerFixture, tmp_path: Path
):
    """Verify os.remove is not called if the partial file was never created."""
    # Arrange
    file_url = "https://example.com/file.zip"
    local_filepath = tmp_path / "never_created.zip"

    mocker.patch("requests.get", side_effect=requests.exceptions.RequestException)
    mocker.patch("os.path.exists", return_value=False)  # Simulate file not existing
    mock_remove = mocker.patch("os.remove")

    # Act
    result = _download_file(file_url, local_filepath)

    # Assert
    assert result is False
    mock_remove.assert_not_called()
