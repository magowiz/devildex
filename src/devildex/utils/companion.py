# src/devildex/tools/project_registrar.py
import argparse
import datetime
import json
import logging
import os
import sys
from pathlib import Path

# È necessario che devildex sia installato o nel PYTHONPATH
# affinché questi import funzionino quando lo script è eseguito con python -m
try:
    from devildex.app_paths import AppPaths
    from devildex.info import APPLICATION_NAME
except ImportError:
    # Fallback per poter eseguire lo script anche se devildex non è nel path
    # Questo è utile per lo sviluppo dello script stesso, ma per l'utente finale
    # l'esecuzione con `python -m` è preferibile.
    print(
        "Errore: Impossibile importare i moduli di DevilDex. "
        "Assicurati che DevilDex sia installato o che lo script sia eseguito "
        "in un contesto dove il pacchetto devildex è trovabile (es. python -m devildex.tools.project_registrar)",
        file=sys.stderr,
    )
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format=f"[%(asctime)s - {APPLICATION_NAME.upper()}_REGISTRAR - %(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)], # Output su stdout per feedback diretto
)
logger = logging.getLogger(__name__)

REGISTRY_SUBDIR = "registered_projects"


def get_current_venv_path() -> Path | None:
    """Tenta di determinare il percorso dell'ambiente virtuale Python corrente.
    """
    # sys.prefix è il modo più affidabile quando si è dentro un venv attivato
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        logger.debug(f"Venv path identificato tramite sys.prefix: {sys.prefix}")
        return Path(sys.prefix)

    # VIRTUAL_ENV è un fallback comune
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        logger.debug(f"Venv path identificato tramite VIRTUAL_ENV: {virtual_env}")
        return Path(virtual_env)

    logger.warning(
        "Impossibile determinare il percorso del venv. "
        "Assicurati che uno script sia eseguito all'interno di un venv attivato."
    )
    return None


def register_project(project_path_str: str | None) -> None:
    """Raccoglie informazioni sul progetto e il venv corrente e le salva
    in un file nella directory dati di DevilDex.
    """
    venv_path = get_current_venv_path()
    if not venv_path:
        logger.error(
            "Operazione annullata: impossibile determinare l'ambiente virtuale."
        )
        return

    if project_path_str:
        project_path = Path(project_path_str).resolve()
        if not project_path.is_dir():
            logger.error(f"Il percorso del progetto specificato non è una directory valida: {project_path}")
            return
    else:
        project_path = Path(os.getcwd()).resolve()
        logger.info(f"Utilizzo della directory corrente come percorso del progetto: {project_path}")

    project_name = project_path.name

    app_paths_manager = AppPaths()
    registry_dir = app_paths_manager.user_data_dir / REGISTRY_SUBDIR
    registry_dir.mkdir(parents=True, exist_ok=True)

    # Usiamo il nome del progetto per il file JSON, normalizzandolo un po'
    safe_project_name = "".join(
        c if c.isalnum() or c in ("_", "-") else "_" for c in project_name
    )
    if not safe_project_name:
        safe_project_name = "unnamed_project"

    registration_file = registry_dir / f"{safe_project_name}.json"

    project_data = {
        "project_name": project_name,
        "project_path": str(project_path),
        "venv_path": str(venv_path),
        "python_executable": sys.executable, # L'interprete Python del venv
        "registration_timestamp_utc": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "devildex_version_at_registration": getattr(sys.modules.get("devildex.info"), "VERSION", "unknown")
    }

    try:
        with open(registration_file, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=4)
        logger.info(f"Progetto '{project_name}' registrato con successo!")
        logger.info(f"Percorso Venv: {venv_path}")
        logger.info(f"Percorso Progetto: {project_path}")
        logger.info(f"File di registrazione: {registration_file}")
    except OSError as e:
        logger.error(
            f"Errore durante la scrittura del file di registrazione {registration_file}: {e}"
        )
    except Exception: # pylint: disable=broad-except
        logger.exception(
            f"Errore imprevisto durante la registrazione del progetto {project_name}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Registra il progetto corrente e il suo ambiente virtuale con DevilDex. "
            "Questo script dovrebbe essere eseguito dall'interno del venv attivato "
            "del progetto che si desidera registrare."
        )
    )
    parser.add_argument(
        "--project-path",
        type=str,
        default=None,
        help=(
            "Percorso opzionale alla directory root del progetto. "
            "Se non fornito, viene usata la directory di lavoro corrente."
        ),
    )
    args = parser.parse_args()

    logger.info("Avvio registrazione progetto per DevilDex...")
    register_project(args.project_path)


if __name__ == "__main__":
    main()
