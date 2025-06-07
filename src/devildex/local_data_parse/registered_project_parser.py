"""module that parse a registered project data."""

import json
import logging
from pathlib import Path
from typing import Optional, TypedDict

from devildex.app_paths import AppPaths

logger = logging.getLogger(__name__)


REGISTRATION_FILE_NAME = "current_registered_project.json"
REGISTRY_SUBDIR = "registered_projects"


class RegisteredProjectData(TypedDict, total=False):
    """Class that implements RegisteredProjectData."""

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
                except (TypeError, OSError, RuntimeError):
                    logger.warning(
                        f"Percorso non valido per '{path_key}' in "
                        f"{file_path}: {data[path_key]}"
                    )

    except FileNotFoundError:
        logger.info(
            "File di registrazione non trovato durante " f"il parsing: {file_path}"
        )
        return None
    except json.JSONDecodeError:
        logger.exception(f"Errore nel decodificare il JSON dal file: {file_path}")
        return None
    except Exception:  # pylint: disable=broad-except
        logger.exception(f"Errore imprevisto durante il parsing del file: {file_path}")
        return None
    else:
        return data


def save_active_registered_project(project_data: RegisteredProjectData) -> bool:
    """Salva i dati del progetto fornito come progetto attivamente registrato.

    Crea la directory necessaria se non esiste e scrive i dati del progetto
    in formato JSON nel file di registrazione.

    Args:
        project_data: Un dizionario contenente i dettagli del progetto da salvare.
                      Dovrebbe conformarsi alla struttura RegisteredProjectData.

    Returns:
        True se il salvataggio ha avuto successo, False altrimenti.

    """
    try:
        app_paths = AppPaths()
        registry_base_dir = app_paths.user_data_dir / REGISTRY_SUBDIR

        registry_base_dir.mkdir(parents=True, exist_ok=True)

        registration_file_to_write = registry_base_dir / REGISTRATION_FILE_NAME
    except OSError:
        logger.exception(
            "Errore nel determinare o creare il percorso per il file di registrazione "
            "del progetto attivo"
        )
        return False

    if not registration_file_to_write:
        logger.error(
            "Impossibile determinare il percorso del "
            "file per salvare la registrazione del progetto attivo."
        )
        return False

    try:
        required_keys = ["project_name", "project_path", "python_executable"]
        for key in required_keys:
            if key not in project_data or project_data.get(key) is None:  # type: ignore
                logger.error(
                    "Dati del progetto non validi per il salvataggio: "
                    f"chiave richiesta '{key}' mancante o None."
                )
                return False

        with registration_file_to_write.open("w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=4)
        logger.info(
            f"Progetto '{project_data.get('project_name')}' "
            f"salvato come attivo in: {registration_file_to_write}"
        )

    except OSError:
        logger.exception(
            "Errore di I/O durante il salvataggio del "
            f"progetto attivo in {registration_file_to_write}"
        )
    except TypeError:
        logger.exception(
            "Errore di tipo durante la serializzazione JSON per il"
            f" progetto attivo in {registration_file_to_write}"
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Errore imprevisto durante il salvataggio del "
            f"progetto attivo in {registration_file_to_write}"
        )
    else:
        return True
    return False


def clear_active_registered_project() -> None:
    """Rimuove il file che memorizza lo stato del progetto attivo."""
    try:
        app_paths = AppPaths()
        registry_base_dir = app_paths.user_data_dir / REGISTRY_SUBDIR
        registration_file_to_clear = registry_base_dir / REGISTRATION_FILE_NAME
    except OSError:
        logger.exception(
            "Errore nel determinare il percorso del file di registrazione da pulire."
        )
        return

    if not registration_file_to_clear:
        logger.error(
            "Impossibile determinare il percorso del file di registrazione da pulire."
        )
        return

    try:
        if registration_file_to_clear.exists() and registration_file_to_clear.is_file():
            registration_file_to_clear.unlink()
            logger.info(
                f"File del progetto attivo rimosso: {registration_file_to_clear}"
            )
        else:
            logger.info(
                "Nessun file del progetto attivo da rimuovere "
                f"(non esisteva o non era un file): {registration_file_to_clear}"
            )
    except OSError:
        logger.exception(
            "Errore durante la rimozione del file "
            f"del progetto attivo {registration_file_to_clear}"
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception("Errore imprevisto durante la pulizia del progetto attivo")


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
            logger.debug(
                "La directory base per la registrazione "
                f"({registry_base_dir}) non esiste."
            )
        else:
            registration_file_to_check = registry_base_dir / REGISTRATION_FILE_NAME
    except OSError:
        logger.exception(
            "Errore nel determinare il percorso del " "file di registrazione."
        )

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
        logger.info(
            f"Progetto '{project_data.get('project_name')}'" " caricato con successo."
        )
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
        logger.info(
            "Nessun progetto attivamente registrato trovato o "
            "errore durante il caricamento."
        )
