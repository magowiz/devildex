"""test readthedocs api."""

from unittest.mock import MagicMock, patch

from devildex.readthedocs.readthedocs_api import download_readthedocs_prebuilt_robust


@patch("devildex.readthedocs.readthedocs_api.logger.error")
def test_download_readthedocs_prebuilt_robust_empty_project_slug(
    mock_logger_error: MagicMock,
) -> None:
    """Verify download_readthedocs_prebuilt_robust handles empty project_slug."""
    result = download_readthedocs_prebuilt_robust(project_name="")
    assert result is None
    mock_logger_error.assert_called_once_with(
        "Error: project_slug is empty. Cannot proceed with download."
    )
