import argparse
import datetime
import json
import logging
import os
import sys
from pathlib import Path

try:
    from devildex.app_paths import AppPaths
    from devildex.info import APPLICATION_NAME
    from devildex.info import VERSION as DEVILDEX_VERSION
except ImportError:
    print(
        "Errore: Impossibile importare i moduli di DevilDex. "
        "Assicurati che DevilDex sia installato o che lo script sia eseguito "
        "in un contesto dove il pacchetto devildex è trovabile.",
        file=sys.stderr,
    )
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format=f"[%(asctime)s - {APPLICATION_NAME.upper()}_REGISTRAR - "
           "%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

REGISTRY_SUBDIR = "registered_projects"
FIXED_REGISTRATION_FILE_NAME = "current_registered_project.json"




def get_active_user_venv_info() -> tuple[Path | None, str | None]:
    """Determina il percorso del venv e l'eseguibile Python basandosi
    esclusivamente sulla variabile d'ambiente VIRTUAL_ENV.

    Restituisce:
        tuple[Path | None, str | None]: (percorso_venv_attivo_utente, percorso_eseguibile_python_utente)
                                        o (None, None) se VIRTUAL_ENV non è impostato.
    """
    virtual_env_path_str = os.environ.get("VIRTUAL_ENV")

    if not virtual_env_path_str:
        logger.info(
            "VIRTUAL_ENV non impostato. Impossibile identificare un ambiente virtuale utente attivo."
        )
        return None, None

    venv_path = Path(virtual_env_path_str).resolve()
    logger.debug(f"Venv utente attivo identificato tramite VIRTUAL_ENV: {venv_path}")

    python_exe_name = "python.exe" if os.name == "nt" else "python"
    scripts_dir_name = "Scripts" if os.name == "nt" else "bin"
    python_exe_path = venv_path / scripts_dir_name / python_exe_name

    if python_exe_path.exists() and python_exe_path.is_file():
        logger.debug(
            f"Eseguibile Python per VIRTUAL_ENV utente: {python_exe_path}"
        )
        return venv_path, str(python_exe_path)

    logger.warning(
        f"VIRTUAL_ENV è '{venv_path}', ma l'eseguibile Python atteso "
        f"non è stato trovato in '{python_exe_path}'. "
        "La registrazione del venv potrebbe non essere completa."
    )
    return venv_path, None


def register_project(project_path_str: str | None) -> None:
    """Raccoglie informazioni sul progetto e il venv utente attivo e le salva."""
    active_venv_path, active_python_executable = get_active_user_venv_info()

    if not active_venv_path:
        logger.error(
            "Operazione annullata: nessun ambiente virtuale utente attivo (VIRTUAL_ENV) rilevato. "
            "Assicurati di aver attivato l'ambiente virtuale del progetto che desideri registrare."
        )
        return

    if not active_python_executable:
        logger.error(
            f"Operazione annullata: VIRTUAL_ENV '{active_venv_path}' rilevato, ma impossibile "
            "determinare l'eseguibile Python corretto al suo interno. "
            "Verifica la struttura del tuo ambiente virtuale."
        )
        return

    if project_path_str:
        project_path = Path(project_path_str).resolve()
        if not project_path.is_dir():
            logger.error(
                f"Il percorso del progetto specificato non è una directory valida: {project_path}"
            )
            return
    else:
        project_path = Path(os.getcwd()).resolve()
        logger.info(
            "Utilizzo della directory corrente come percorso del "
            f"progetto: {project_path}"
        )

    project_name = project_path.name

    app_paths_manager = AppPaths()
    registry_dir = app_paths_manager.user_data_dir / REGISTRY_SUBDIR
    registry_dir.mkdir(parents=True, exist_ok=True)

    registration_file = registry_dir / FIXED_REGISTRATION_FILE_NAME


    project_data = {
        "project_name": project_name,
        "project_path": str(project_path),
        "venv_path": str(active_venv_path),
        "python_executable": active_python_executable,
        "registration_timestamp_utc": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "devildex_version_at_registration": DEVILDEX_VERSION,
    }

    try:
        with open(registration_file, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=4)
        logger.info(f"Progetto '{project_name}' registrato con successo!")
        logger.info(f"Percorso Venv utente: {active_venv_path}")
        logger.info(f"Eseguibile Python utente: {active_python_executable}")
        logger.info(f"Percorso Progetto: {project_path}")
        logger.info(f"File di registrazione: {registration_file}")
    except OSError:
        logger.exception(
            "Errore durante la scrittura del file di registrazione "
            f"{registration_file}"
        )
    except Exception: # pylint: disable=broad-except
        logger.exception(
            f"Errore imprevisto durante la registrazione del progetto {project_name}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Registra il progetto corrente e il suo ambiente virtuale con DevilDex. "
            "Questo script dovrebbe essere eseguito dall'interno del venv ATTIVATO "
            "del progetto che si desidera registrare."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--project-path",
        type=str,
        default=None,
        help=(
            "Percorso opzionale alla directory root del progetto.\n"
            "Se non fornito, viene usata la directory di lavoro corrente."
        ),
    )
    args = parser.parse_args()

    logger.info("Avvio registrazione progetto per DevilDex...")
    register_project(args.project_path)


if __name__ == "__main__":
    main()
