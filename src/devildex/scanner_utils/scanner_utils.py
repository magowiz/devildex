import re
from pathlib import Path

def read_file_content_robustly(filepath: Path) -> str | None:
    """
    Read il content di un file in modo robust, handling common errors.

    Args:
        filepath: Il path del file da read.

    Returns:
        Il content del file come string, o None in caso di error.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        print(f"    ⚠️ Unable to read file {filepath} con encoding UTF-8. Could non be un file di testo valido.")
        return None
    except Exception as e:
        print(f"    ❌ Error durante la reading di {filepath}: {e}")
        return None

def find_config_files(base_dirs: list[Path], filename: str) -> list[Path]:
    """
    Cerca a specific configuration file in a list of base directories.

    Args:
        base_dirs: Una lista di objects Path delle directory dove search.
        filename: Il nome del file da search (es. 'conf.py').

    Returns:
        Una lista di objects Path dei file found.
    """
    found_files = []
    for base_dir in base_dirs:
        conf_path = base_dir / filename
        if conf_path.is_file():
            found_files.append(conf_path)
    return found_files

def check_content_patterns(content: str, checks: list[tuple[str, str]], re_flags=0) -> str | None:
    """
    Verify se il content di una string matches a uno dei pattern given regex.

    Args:
        content: La string (es. content di un file) da analyze.
        checks: Una lista di tuple (regex_pattern, success_message).
        re_flags: Flag da pass a re.search (es. re.DOTALL | re.MULTILINE).

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
        content: the string da analyze.
        search_strings: Una lista di strings da search.

    Returns:
        Il numero di strings found nel content.
    """
    count = 0
    for s in search_strings:
        if s in content:
            count += 1
    return count

