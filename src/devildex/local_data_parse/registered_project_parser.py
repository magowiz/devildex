import json
import logging
from pathlib import Path
from typing import Optional, TypedDict

from devildex.app_paths import AppPaths

logger = logging.getLogger(__name__)


REGISTRATION_FILE_NAME = "current_registered_project.json"
REGISTRY_SUBDIR = "registered_projects"


class RegisteredProjectData(TypedDict, total=False):
    project_name: str
    project_path: str
    venv_path: str | None
    python_executable: str | None
    registration_timestamp_utc: str
    devildex_version_at_registration: str



def _parse_registration_content(file_path: Path) -> RegisteredProjectData | None:
    """Legge, parsa e valida il contenuto di un file JSON di registrazione.

    Rinominato con underscore per indicare che è un helper interno.
    """
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        required_keys = ["project_name", "project_path", "python_executable"]
        for key in required_keys:
            if key not in data or data[key] is None:
                logger.error(
                    f"Chiave richiesta '{key}' mancante o None nel file: {file_path}"
                )
                return None

        for path_key in ["project_path", "venv_path", "python_executable"]:
            if path_key in data and data[path_key] is not None:
                try:
                    _ = Path(data[path_key]).resolve()
                    data[path_key] = str(Path(data[path_key]))
                except Exception: # pylint: disable=broad-except
                    logger.warning(f"Percorso non valido per '{path_key}' in "
                                   f"{file_path}: {data[path_key]}")
        return data

    except FileNotFoundError:
        logger.info(f"File di registrazione non trovato durante il parsing: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.exception(f"Errore nel decodificare il JSON dal file: {file_path}")
        return None
    except Exception: # pylint: disable=broad-except
        logger.exception(f"Errore imprevisto durante il parsing del file: {file_path}")
        return None


def load_active_registered_project() -> Optional[RegisteredProjectData]:
    """Carica e parsa il progetto attivamente registrato.

    Determina il percorso del file, lo legge e ne valida il contenuto.
    Restituisce i dati del progetto o None se non registrato o in caso di errore.
    """
    registration_file_to_check: Optional[Path] = None
    try:
        app_paths = AppPaths()
        registry_base_dir = app_paths.user_data_dir / REGISTRY_SUBDIR
        if not registry_base_dir.exists():
            logger.debug("La directory base per la registrazione "
                         f"({registry_base_dir}) non esiste.")
        else:
            registration_file_to_check = registry_base_dir / REGISTRATION_FILE_NAME
    except Exception: # pylint: disable=broad-except
        logger.exception("Errore nel determinare il percorso del "
                         "file di registrazione.")

    if not registration_file_to_check:
        logger.info("Percorso del file di registrazione non determinabile.")
        return None

    if not registration_file_to_check.is_file():
        logger.info(
            "Nessun progetto attivamente registrato trovato "
            f"(file mancante: {registration_file_to_check})."
        )
        return None

    logger.debug(f"Trovato file di progetto registrato: {registration_file_to_check}")
    project_data = _parse_registration_content(registration_file_to_check)

    if project_data:
        logger.info(f"Progetto '{project_data.get('project_name')}' caricato con successo.")
    return project_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    active_project = load_active_registered_project()
    if active_project:
        logger.info("Progetto attivamente registrato caricato:")
        logger.info(f"  - Nome: {active_project.get('project_name')}")
        logger.info(f"  - Percorso Venv: {active_project.get('venv_path')}")
        logger.info(f"  - Eseguibile Python: {active_project.get('python_executable')}")
    else:
        logger.info("Nessun progetto attivamente registrato trovato o "
                    "errore durante il caricamento.")
