import re
from pathlib import Path

def read_file_content_robustly(filepath: Path) -> str | None:
    """
    Read file content in a robust way, handling common errors.

    Args:
        filepath: path of file to read.

    Returns:
        file content as a string, or None in case of error.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        print(f"    ⚠️ Unable to read file {filepath} con encoding UTF-8. Could not be a valid text file.")
        return None
    except Exception as e:
        print(f"    ❌ Error during reading {filepath}: {e}")
        return None

def find_config_files(base_dirs: list[Path], filename: str) -> list[Path]:
    """
    Search a specific configuration file in a list of base directories.

    Args:
        base_dirs: a list of Path objects of directories to search.
        filename: name of the file to search (ex. 'conf.py').

    Returns:
        a list of Path objects of the  found files.
    """
    found_files = []
    for base_dir in base_dirs:
        conf_path = base_dir / filename
        if conf_path.is_file():
            found_files.append(conf_path)
    return found_files

def check_content_patterns(content: str, checks: list[tuple[str, str]], re_flags=0) -> str | None:
    """
    Verify if a string content matches one of given pattern regex.

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
    """
    Count how many given strings are into content.

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

