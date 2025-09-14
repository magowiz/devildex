"""Real integration tests for the VCS fallback mechanisms in PackageSourceFetcher.

These tests make real network calls and use the git command. They are marked as
'integration' and may be slow.
"""

import logging
import tempfile
from pathlib import Path

import pytest

from devildex.fetcher import PackageSourceFetcher

logger = logging.getLogger(__name__)

PACKAGE_NAME = "requests"
PACKAGE_VERSION = "2.25.1"
REPO_URL = "https://github.com/psf/requests.git"
EXPECTED_TAG = f"v{PACKAGE_VERSION}"


@pytest.fixture
def fetcher_and_path() -> tuple[PackageSourceFetcher, Path]:
    """Provide a PackageSourceFetcher instance and a temporary directory for a test."""
    with tempfile.TemporaryDirectory(prefix="devildex_real_vcs_") as tmpdir:
        tmp_path = Path(tmpdir)
        package_info = {"name": PACKAGE_NAME, "version": PACKAGE_VERSION}
        fetcher = PackageSourceFetcher(
            base_save_path=str(tmp_path), package_info_dict=package_info
        )
        yield fetcher, tmp_path


def _verify_downloaded_content(download_path: Path) -> bool:
    """Verify that the downloaded content is the right version of 'requests'."""
    if not download_path.exists() or not any(download_path.iterdir()):
        logger.error(
            "Verification failed: Download directory is empty or does not exist."
        )
        return False

    version_file = download_path / "requests" / "__version__.py"
    if not version_file.exists():
        logger.error(f"Verification failed: Version file not found at {version_file}")
        return False

    content = version_file.read_text()
    expected_string = f"__version__ = '{PACKAGE_VERSION}'"
    if expected_string not in content:
        logger.error(
            f"Verification failed: Expected string '{expected_string}' not in"
            f" {version_file.name}"
        )
        logger.error(f"File content was: {content}")
        return False

    logger.info("Verification of downloaded content PASSED.")
    return True


@pytest.mark.integration
def test_real_github_archive_fails_correctly(
    fetcher_and_path: tuple[PackageSourceFetcher, Path],
) -> None:
    """Tests that the first fallback correctly fails."""
    fetcher, _ = fetcher_and_path
    logger.info("Testing that _try_fetch_tag_github_archive correctly fails...")

    tag_variations = [PACKAGE_VERSION, EXPECTED_TAG]
    success = fetcher._try_fetch_tag_github_archive(REPO_URL, tag_variations)

    assert not success, "Expected direct archive download to fail, but it succeeded."
    logger.info("_try_fetch_tag_github_archive correctly returned False.")


@pytest.mark.integration
def test_real_shallow_clone_succeeds(
    fetcher_and_path: tuple[PackageSourceFetcher, Path],
) -> None:
    """Tests that the second fallback succeeds and fetches the correct source."""
    fetcher, _ = fetcher_and_path
    logger.info("Testing that _try_fetch_tag_shallow_clone succeeds...")

    tag_variations = [PACKAGE_VERSION, EXPECTED_TAG]
    success = fetcher._try_fetch_tag_shallow_clone(REPO_URL, tag_variations)

    assert success, "Shallow clone failed, but it was expected to succeed."
    assert _verify_downloaded_content(fetcher.download_target_path)


@pytest.mark.integration
def test_real_full_clone_checkout_succeeds(
    fetcher_and_path: tuple[PackageSourceFetcher, Path],
) -> None:
    """Tests that the third fallback succeeds and fetches the correct source."""
    fetcher, _ = fetcher_and_path
    logger.info("Testing that _try_fetch_tag_full_clone_checkout succeeds...")

    tag_variations = [PACKAGE_VERSION, EXPECTED_TAG]
    success = fetcher._try_fetch_tag_full_clone_checkout(REPO_URL, tag_variations)

    assert success, "Full clone and checkout failed, but it was expected to succeed."
    assert _verify_downloaded_content(fetcher.download_target_path)
