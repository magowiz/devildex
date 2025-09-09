"""Tests for the deps_utils module."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pip_requirements_parser import RequirementsFile

from devildex.utils.deps_utils import (
    _process_requirements_obj,
    filter_requirements_lines,
)

EXPECTED_DEBUG_CALL_COUNT = 2


@patch("devildex.utils.deps_utils.RequirementsFile", None)
def test_filter_requirements_lines_requirements_file_none(
    cap_log: pytest.LogCaptureFixture,
) -> None:
    """Verify filter_requirements_lines handles RequirementsFile being None."""
    with cap_log.at_level(logging.ERROR):
        result = filter_requirements_lines("/fake/path/reqs.txt")
    assert result is None
    assert "The 'pip-requirements-parser' package is not installed." in cap_log.text


def test_process_requirements_obj_invalid_lines(
    cap_log: pytest.LogCaptureFixture,
) -> None:
    """Verify _process_requirements_obj logs warning for invalid lines."""
    mock_req_file = MagicMock(spec=RequirementsFile)
    mock_req_file.requirements = []
    mock_req_file.invalid_lines = [
        MagicMock(line="invalid line 1"),
        MagicMock(line="invalid line 2"),
        MagicMock(line=""),
        MagicMock(line=None),
    ]

    with cap_log.at_level(logging.WARNING):
        result = _process_requirements_obj(mock_req_file, Path("/fake/reqs.txt"), set())

    assert result == []
    assert len(cap_log.records) == 1
    record = cap_log.records[0]
    assert "Found 2 RS ROWS NOT VALID" in record.message
    assert "in ' /fake/reqs.txt'." in record.message


def test_process_requirements_obj_explicit_removal(
    cap_log: pytest.LogCaptureFixture,
) -> None:
    """Verify _process_requirements_obj handles explicit removal lines."""
    mock_req_file = MagicMock(spec=RequirementsFile)
    mock_req_file.requirements = [
        MagicMock(line="-e ."),
        MagicMock(line="valid-dep"),
    ]
    mock_req_file.invalid_lines = []

    lines_to_remove = {"-e ."}
    with cap_log.at_level(logging.INFO):
        result = _process_requirements_obj(
            mock_req_file, Path("/fake/reqs.txt"), lines_to_remove
        )

    assert result == ["valid-dep"]
    assert "Explicit removal of the line '-e .' from '/fake/reqs.txt'" in cap_log.text


@patch("devildex.utils.deps_utils.logger.error")
@patch("pathlib.Path.exists", return_value=False)
def test_filter_requirements_lines_file_not_found(
    mock_exists: MagicMock, mock_logger_error: MagicMock
) -> None:
    """Verify filter_requirements_lines handles file not found."""
    result = filter_requirements_lines("/fake/path/non_existent.txt")
    assert result is None
    mock_logger_error.assert_called_once_with(
        "requirements file '%s' not found.", Path("/fake/path/non_existent.txt")
    )


@patch("devildex.utils.deps_utils.logger.debug")
@patch("devildex.utils.deps_utils.RequirementsFile.from_file")
@patch("pathlib.Path.exists", return_value=True)
def test_filter_requirements_lines_success(
    mock_exists: MagicMock, mock_from_file: MagicMock, mock_logger_debug: MagicMock
) -> None:
    """Verify filter_requirements_lines successfully filters lines."""
    mock_req_file = MagicMock(spec=RequirementsFile)
    mock_req_file.requirements = [
        MagicMock(line="requests"),
        MagicMock(line="-e ."),
    ]
    mock_req_file.invalid_lines = []
    mock_from_file.return_value = mock_req_file

    result = filter_requirements_lines("/fake/path/reqs.txt")

    assert result == ["requests"]
    mock_from_file.assert_called_once_with("/fake/path/reqs.txt")

    # Assert both debug calls
    assert mock_logger_debug.call_count == EXPECTED_DEBUG_CALL_COUNT
    mock_logger_debug.assert_any_call(
        "Attempt to parse and filter: %s", Path("/fake/path/reqs.txt")
    )
    mock_logger_debug.assert_any_call(
        "Numero di rows valid extract da '%s': %s", Path("/fake/path/reqs.txt"), 1
    )


@patch("devildex.utils.deps_utils.logger.exception")
@patch(
    "devildex.utils.deps_utils.RequirementsFile.from_file",
    side_effect=OSError("Read error"),
)
@patch("pathlib.Path.exists", return_value=True)
def test_filter_requirements_lines_os_error(
    mock_exists: MagicMock, mock_from_file: MagicMock, mock_logger_exception: MagicMock
) -> None:
    """Verify filter_requirements_lines handles OSError during parsing."""
    result = filter_requirements_lines("/fake/path/reqs.txt")
    assert result is None
    mock_logger_exception.assert_called_once()
    assert (
        "Decode or I/O error during parsing file '%s'"
        in mock_logger_exception.call_args[0][0]
    )
    assert Path("/fake/path/reqs.txt") in mock_logger_exception.call_args[0]


@patch("devildex.utils.deps_utils.logger.exception")
@patch(
    "devildex.utils.deps_utils.RequirementsFile.from_file",
    side_effect=UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid byte"),
)
@patch("pathlib.Path.exists", return_value=True)
def test_filter_requirements_lines_unicode_error(
    mock_exists: MagicMock, mock_from_file: MagicMock, mock_logger_exception: MagicMock
) -> None:
    """Verify filter_requirements_lines handles UnicodeDecodeError during parsing."""
    result = filter_requirements_lines("/fake/path/reqs.txt")
    assert result is None
    mock_logger_exception.assert_called_once()
    assert (
        "Decode or I/O error during parsing file '%s'"
        in mock_logger_exception.call_args[0][0]
    )
    assert Path("/fake/path/reqs.txt") in mock_logger_exception.call_args[0]
