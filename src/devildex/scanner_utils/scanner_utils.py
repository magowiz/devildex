import os
import re
import shutil
from pathlib import Path

def read_file_content_robustly(filepath: Path) -> str | None:
    """
    Legge il contenuto di un file in modo robusto, gestendo errori comuni.

    Args:
        filepath: Il percorso del file da leggere.

    Returns:
        Il contenuto del file come stringa, o None in caso di errore.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        print(f"    ⚠️ Impossibile leggere il file {filepath} con encoding UTF-8. Potrebbe non essere un file di testo valido.")
        return None
    except Exception as e:
        print(f"    ❌ Errore durante la lettura di {filepath}: {e}")
        return None

def find_config_files(base_dirs: list[Path], filename: str) -> list[Path]:
    """
    Cerca un file di configurazione specifico in una lista di directory base.

    Args:
        base_dirs: Una lista di oggetti Path delle directory dove cercare.
        filename: Il nome del file da cercare (es. 'conf.py').

    Returns:
        Una lista di oggetti Path dei file trovati.
    """
    found_files = []
    for base_dir in base_dirs:
        conf_path = base_dir / filename
        if conf_path.is_file():
            found_files.append(conf_path)
    return found_files

def check_content_patterns(content: str, checks: list[tuple[str, str]], re_flags=0) -> str | None:
    """
    Verifica se il contenuto di una stringa corrisponde a uno dei pattern regex forniti.

    Args:
        content: La stringa (es. contenuto di un file) da analizzare.
        checks: Una lista di tuple (regex_pattern, success_message).
        re_flags: Flag da passare a re.search (es. re.DOTALL | re.MULTILINE).

    Returns:
        Il messaggio di successo del primo pattern corrispondente, o None se nessuno corrisponde.
    """
    for pattern, message in checks:
        if re.search(pattern, content, re_flags):
            return message
    return None

def count_matching_strings(content: str, search_strings: list[str]) -> int:
    """
    Conta quante delle stringhe fornite sono presenti nel contenuto.

    Args:
        content: La stringa da analizzare.
        search_strings: Una lista di stringhe da cercare.

    Returns:
        Il numero di stringhe trovate nel contenuto.
    """
    count = 0
    for s in search_strings:
        if s in content:
            count += 1
    return count

