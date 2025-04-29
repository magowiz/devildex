# scan_project_env.py
# Questo script è destinato a essere eseguito come subprocess
# nell'ambiente Python di un progetto esterno scansionato da DevilDex.

import os
import sys

try:
    import toml
except ImportError:
    print(
        "Error: Il pacchetto 'toml' non è installabile o non presente "
        "nell'ambiente scansionato.",
        file=sys.stderr,
    )
    sys.exit(1)


def find_pyproject_toml(start_path="."):
    """Cerca pyproject.toml nella directory corrente o nelle directory genitore.
    Restituisce il percorso assoluto o None se non trovato.
    """
    current_path = os.path.abspath(start_path)
    while True:
        pyproject_path = os.path.join(current_path, "pyproject.toml")
        if os.path.exists(pyproject_path):
            return pyproject_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            return None
        current_path = parent_path


def _read_project_data_toml(pyproject_path):
    try:
        with open(pyproject_path, "r") as f:
            pyproject_data = toml.load(f)
    except FileNotFoundError:
        print(
            f"Errore: File pyproject.toml non trovato a {pyproject_path}.",
            file=sys.stderr,
        )
        return set()
    except toml.TomlDecodeError:
        print(
            f"Errore: Impossibile decodificare il file TOML a {pyproject_path}.",
            file=sys.stderr,
        )
        return set()
    return pyproject_data


def get_explicit_poetry_dependencies(pyproject_path):
    """Legge pyproject.toml e restituisce un set con i nomi delle dipendenze dirette
    (dalle sezioni tool.poetry.dependencies e tool.poetry.group.*.dependencies).
    """

    pyproject_data = _read_project_data_toml(pyproject_path)
    explicit_deps = set()

    def add_deps_from_section(section_data):
        if isinstance(section_data, dict):
            for name in section_data.keys():
                normalized_name = name.lower().replace("_", "-")
                if normalized_name != "python":
                    explicit_deps.add(normalized_name)

    if (
        "tool" in pyproject_data
        and "poetry" in pyproject_data["tool"]
        and "dependencies" in pyproject_data["tool"]["poetry"]
    ):
        add_deps_from_section(pyproject_data["tool"]["poetry"]["dependencies"])

    if (
        "tool" in pyproject_data
        and "poetry" in pyproject_data["tool"]
        and "group" in pyproject_data["tool"]["poetry"]
    ):
        for group_name, group_data in pyproject_data["tool"]["poetry"]["group"].items():
            if isinstance(group_data, dict) and "dependencies" in group_data:
                add_deps_from_section(group_data["dependencies"])

    return explicit_deps


if __name__ == "__main__":
    pyproject_path1 = find_pyproject_toml(".")

    if not pyproject_path1:
        print(
            "Error: pyproject.toml non trovato. "
            "Impossibile determinare dipendenze esplicite.",
            file=sys.stderr,
        )
        sys.exit(1)

    explicit_package_names = get_explicit_poetry_dependencies(pyproject_path1)

    if not explicit_package_names:
        print(
            "Avviso: Nessuna dipendenza esplicita trovata in "
            "pyproject.toml (oltre a python).",
            file=sys.stderr,
        )
        pass

    sys.exit(0)
