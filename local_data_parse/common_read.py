import os
import sys

import toml
from packaging.requirements import Requirement


def find_pyproject_toml(start_path="."):
    """Cerca pyproject.toml nella directory start_path e nelle sue directory genitore.
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


def add_deps_from_section(section_data, explicit_deps):
    if isinstance(section_data, dict):
        for name in section_data.keys():
            normalized_name = name.lower().replace("_", "-")
            if normalized_name != "python":
                explicit_deps.add(normalized_name)


def get_explicit_poetry_dependencies(pyproject_path):
    """Read pyproject.toml and returns a set con i nomi delle dipendenze dirette
    (dalle sezioni tool.poetry.dependencies e tool.poetry.group.*.dependencies).
    Richiede che 'toml' sia importabile.

    Args:
        pyproject_path (str): Il percorso al file pyproject.toml.

    Returns:
        set: Un set di stringhe contenente i nomi delle dipendenze esplicite.
             Ritorna un set vuoto se il file non esiste, non è leggibile,
             non è un progetto Poetry valido, o non ha dipendenze esplicite.
    """
    explicit_deps = set()
    if not pyproject_path:
        return explicit_deps

    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            pyproject_data = toml.load(f)
    except FileNotFoundError:
        return explicit_deps
    except toml.TomlDecodeError:
        print(
            f"Warning: Invalid TOML in {pyproject_path}. "
            "Cannot read explicit dependencies.",
            file=sys.stderr,
        )
        return explicit_deps
    except Exception as e:
        print(
            f"Warning: Unexpected error reading {pyproject_path}: {e}", file=sys.stderr
        )
        return explicit_deps

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
                add_deps_from_section(group_data["dependencies"], explicit_deps)

    return explicit_deps


def find_requirements_txt(start_path="."):
    """Cerca requirements.txt nella directory start_path e nelle sue directory genitore.
    Restituisce il percorso assoluto o None se non trovato.
    (Simile a find_pyproject_toml)
    """
    current_path = os.path.abspath(start_path)
    while True:
        reqs_path = os.path.join(current_path, "requirements.txt")
        if os.path.exists(reqs_path):
            return reqs_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            return None
        current_path = parent_path


def get_explicit_package_names_from_requirements(requirements_filepath):
    """Legge un file requirements.txt e restituisce un set con i nomi dei pacchetti espliciti.
    Usa packaging.requirements per un parsing robusto.
    Richiede che 'packaging' sia importabile.

    Args:
        requirements_filepath (str): Il percorso al file requirements.txt.

    Returns:
        set: Un set di stringhe contenente i nomi dei pacchetti espliciti.
             Ritorna un set vuoto se il file non esiste o ci sono errori di lettura/parsing.
    """
    explicit_package_names = set()

    if not requirements_filepath:
        return explicit_package_names

    if not os.path.exists(requirements_filepath):
        print(
            f"Warning: File requirements.txt not found at {requirements_filepath}.",
            file=sys.stderr,
        )
        return explicit_package_names

    try:
        with open(requirements_filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if (
                    not line
                    or line.startswith("#")
                    or line.startswith("-")
                    or line.startswith("--")
                ):
                    continue

                try:
                    req = Requirement(line)
                    explicit_package_names.add(req.name)
                except Exception as e:
                    print(
                        f"Warning: Error parsing line in {requirements_filepath}: '{line}' - {e}",
                        file=sys.stderr,
                    )

    except Exception as e:
        print(f"Error reading {requirements_filepath}: {e}", file=sys.stderr)
        return set()

    return explicit_package_names


def get_explicit_dependencies_from_project_config(start_path="."):
    """Cerca i file di configurazione del progetto (pyproject.toml o requirements.txt)
    a partire da start_path e restituisce un set con i nomi delle dipendenze esplicite.
    Dà priorità a pyproject.toml.

    Args:
        start_path (str): La directory da cui iniziare la ricerca (es. '.' per la CWD).

    Returns:
        set: Un set di stringhe con i nomi delle dipendenze esplicite.
             Ritorna un set vuoto se nessun file di configurazione valido viene trovato
             o se ci sono errori di lettura/parsing.
             Stampa warning/error su stderr.
    """
    pyproject_path = find_pyproject_toml(start_path)
    if pyproject_path:
        print(f"Info: Found pyproject.toml at {pyproject_path}", file=sys.stderr)
        return get_explicit_poetry_dependencies(pyproject_path)

    reqs_path = find_requirements_txt(start_path)
    if reqs_path:
        print(f"Info: Found requirements.txt at {reqs_path}", file=sys.stderr)
        return get_explicit_package_names_from_requirements(reqs_path)

    print(
        f"Warning: No pyproject.toml or requirements.txt found starting from {start_path}. "
        f"Cannot determine explicit dependencies.",
        file=sys.stderr,
    )
    return set()


if __name__ == "__main__":
    print("--- Testing project_config.py directly ---", file=sys.stderr)

    explicit_names = get_explicit_dependencies_from_project_config(".")

    if explicit_names:
        print("\n--- Explicit Dependency Names Found ---", file=sys.stderr)
        for name in sorted(list(explicit_names)):
            print(f"- {name}", file=sys.stderr)
        print("--- End Explicit Dependency Names ---", file=sys.stderr)
        sys.exit(0)
    else:
        print(
            "\n--- No explicit dependency names found or config file missing ---",
            file=sys.stderr,
        )
        sys.exit(1)
