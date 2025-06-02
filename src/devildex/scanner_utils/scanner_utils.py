"""scanner utils module."""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

def read_file_content_robustly(filepath: Path) -> str | None:
    """Read file content in a robust way, handling common errors.

    Args:
        filepath: path of file to read.

    Returns:
        file content as a string, or None in case of error.

    """
    try:
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        logger.exception(
            f"    ⚠️ Unable to read file {filepath} con encoding UTF-8. "
            "Could not be a valid text file."
        )
        return None
    except OSError:
        logger.exception(f"    ❌ Error reading file{filepath}")
        return None


def find_config_files(base_dirs: list[Path], filename: str) -> list[Path]:
    """Search a specific configuration file in a list of base directories.

    It first checks for the file directly in each base_dir. If found,
    these direct matches are returned immediately.
    Otherwise, it performs a recursive search within each base_dir,
    deduplicates the results by their resolved paths, and returns them sorted.

    Args:
        base_dirs: a list of Path objects of directories to search.
        filename: name of the file to search (ex. 'conf.py').

    Returns:
        a list of Path objects of the found files.

    """
    direct_found_files: list[Path] = []
    for base_dir in base_dirs:
        conf_path = base_dir / filename
        if conf_path.is_file():
            direct_found_files.append(conf_path)

    if direct_found_files:
        return direct_found_files

    return _find_recursive_deduplicate_and_sort(base_dirs, filename)


def _find_recursive_deduplicate_and_sort(
    base_dirs: list[Path], filename: str
) -> list[Path]:
    """Perform a recursive search for filename in base_dirs.

    then deduplicates (by resolved path) and sorts the results.
    """
    recursive_finds: list[Path] = []
    for base_dir in base_dirs:
        if base_dir.is_dir():
            found_in_dir = list(base_dir.rglob(filename))
            if found_in_dir:
                recursive_finds.extend(found_in_dir)

    if not recursive_finds:
        return []

    unique_paths_str = set()
    unique_files_final: list[Path] = []
    for p in recursive_finds:
        try:
            resolved_path_str = str(p.resolve())
            if resolved_path_str not in unique_paths_str:
                unique_paths_str.add(resolved_path_str)
                unique_files_final.append(p)
        except FileNotFoundError:
            logger.exception(
                f"    ⚠️ Path {p} could not be resolved during deduplication, skipping."
            )
            continue

    return sorted(unique_files_final)


def check_content_patterns(
    content: str, checks: list[tuple[str, str]], re_flags: re.RegexFlag = 0
) -> str | None:
    """Verify if a string content matches one of given pattern regex.

    Args:
        content: string (ex. file content) da analyze.
        checks: a list of tuples (regex_pattern, success_message).
        re_flags: Flag to pass to re.search (es. re.DOTALL | re.MULTILINE).

    Returns:
        success message of first matching pattern, o None if nothing matches.

    """
    for pattern, message in checks:
        if re.search(pattern, content, re_flags):
            return message
    return None


def count_matching_strings(content: str, search_strings: list[str]) -> int:
    """Count how many given strings are into content.

    Args:
        content: the string to analyze.
        search_strings: a list of strings to search.

    Returns:
        number of strings found in content.

    """
    count = 0
    for s in search_strings:
        if s in content:
            count += 1
    return count
