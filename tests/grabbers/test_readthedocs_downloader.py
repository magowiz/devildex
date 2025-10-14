"""Test for readthedocs api."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from devildex.grabbers.readthedocs_downloader import ReadTheDocsDownloader
from devildex.orchestrator.context import BuildContext

logger = logging.getLogger(__name__)


@pytest.fixture
def rtd_downloader() -> ReadTheDocsDownloader:
    """Fixture for ReadTheDocsDownloader instance."""
    return ReadTheDocsDownloader()


@pytest.fixture
def mock_build_context(mocker: MockerFixture) -> BuildContext:
    """Fixture for a mock BuildContext."""
    context = BuildContext(
        project_name="test_project",
        project_version="latest",
        base_output_dir=Path("/tmp/output"),
        source_root=Path("/tmp/source"),
        project_slug="test_project",
        version_identifier="latest",
        project_root_for_install=Path("/tmp/install"),
        project_url="http://example.com",
        doc_type="readthedocs",  # This is key for can_handle
    )
    return context


@patch("devildex.grabbers.readthedocs_downloader.logger.error")
def test_generate_docset_empty_project_slug(
    mock_logger_error: MagicMock,
    rtd_downloader: ReadTheDocsDownloader,
    mock_build_context: BuildContext,
) -> None:
    """Verify generate_docset handles empty project_slug in BuildContext."""
    mock_build_context.project_slug = ""
    result = rtd_downloader.generate_docset(
        source_path=Path("/tmp/source"),
        output_path=Path("/tmp/output"),
        context=mock_build_context,
    )
    assert result is False
    mock_logger_error.assert_called_once_with(
        "Error: project_slug is empty in BuildContext. Cannot proceed with download."
    )


def test_can_handle_returns_true_for_readthedocs(
    rtd_downloader: ReadTheDocsDownloader, mock_build_context: BuildContext
) -> None:
    """Verify can_handle returns True when doc_type is 'readthedocs'."""
    assert rtd_downloader.can_handle(Path("/tmp/source"), mock_build_context) is True


def test_can_handle_returns_false_for_other_doc_types(
    rtd_downloader: ReadTheDocsDownloader, mock_build_context: BuildContext
) -> None:
    """Verify can_handle returns False for other doc_types."""
    mock_build_context.doc_type = "sphinx"
    assert rtd_downloader.can_handle(Path("/tmp/source"), mock_build_context) is False

    mock_build_context.doc_type = "mkdocs"
    assert rtd_downloader.can_handle(Path("/tmp/source"), mock_build_context) is False

    mock_build_context.doc_type = "docstrings"
    assert rtd_downloader.can_handle(Path("/tmp/source"), mock_build_context) is False
