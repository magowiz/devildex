"""Tests for the version selection logic in the ReadTheDocs API client."""

import pytest

from devildex.readthedocs.readthedocs_api import _choose_best_version

# --- Tests for _choose_best_version ---


@pytest.fixture
def sample_versions() -> list[dict]:
    """Provide a sample list of version dictionaries from the RTD API."""
    return [
        {"slug": "stable", "active": True, "built": True},
        {"slug": "latest", "active": True, "built": True},
        {"slug": "v2.0", "active": True, "built": True},
        {"slug": "v1.0", "active": True, "built": True},
        {"slug": "dev", "active": False, "built": True},  # Not active
        {"slug": "feature-branch", "active": True, "built": False},  # Not built
    ]


def test_choose_best_version_finds_first_preference(
    sample_versions: list[dict],
) -> None:
    """Verify it selects the first preferred version if available."""
    preferred = ["stable", "latest"]
    result = _choose_best_version(sample_versions, preferred)
    assert result == "stable"


def test_choose_best_version_finds_second_preference(
    sample_versions: list[dict],
) -> None:
    """Verify it selects the second preferred version if the first is not ideal."""
    # Make 'stable' unavailable
    sample_versions[0]["active"] = False
    preferred = ["stable", "latest"]
    result = _choose_best_version(sample_versions, preferred)
    assert result == "latest"


def test_choose_best_version_falls_back_to_first_available(
    sample_versions: list[dict],
) -> None:
    """Check it falls back to first active and built version if no preferences match."""
    preferred = ["nonexistent-v1", "nonexistent-v2"]
    result = _choose_best_version(sample_versions, preferred)
    # It should skip inactive/unbuilt versions and pick the first valid one
    assert result == "stable"


def test_choose_best_version_handles_no_active_built_versions() -> None:
    """Verify it returns None if no versions are active and built."""
    versions = [
        {"slug": "stable", "active": False, "built": True},
        {"slug": "latest", "active": True, "built": False},
    ]
    preferred = ["stable", "latest"]
    result = _choose_best_version(versions, preferred)
    assert result is None


def test_choose_best_version_handles_empty_version_list() -> None:
    """Verify it returns None for an empty list of available versions."""
    preferred = ["stable", "latest"]
    result = _choose_best_version([], preferred)
    assert result is None
