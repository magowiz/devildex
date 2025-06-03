"""app paths module."""
import logging
from pathlib import Path

import platformdirs

from devildex.info import APPLICATION_AUTHOR, APPLICATION_NAME

logger = logging.getLogger(__name__)
class AppPaths:
    """Gestisce i percorsi standard per i file di dati, configurazione.

    cache e log dell'applicazione in modo indipendente dalla piattaforma.
    """

    def __init__(self, app_name: str = APPLICATION_NAME,
                 app_author: str = APPLICATION_AUTHOR, version: str | None = None):
        """Inizializza i percorsi.

        Args:
            app_name: Il nome dell'applicazione.
            app_author: L'autore/organizzazione dell'applicazione.
            version: Una versione opzionale dell'app, per percorsi versionati.

        """
        self._dirs = platformdirs.PlatformDirs(
            appname=app_name, appauthor=app_author, version=version)

    @property
    def user_data_dir(self) -> Path:
        """Directory per i file di dati specifici dell'utente.

        Es. Linux:   ~/.local/share/devildex
        Es. macOS:   ~/Library/Application Support/devildex
        Es. Windows: C:\\Users\\<Utente>\\AppData\\Roaming\\DevilDexTeam\\devildex
        """
        path = Path(self._dirs.user_data_dir)
        path.mkdir(parents=True, exist_ok=True) # Assicura che la directory esista
        return path

    @property
    def user_config_dir(self) -> Path:
        """Directory per i file di configurazione specifici dell'utente.

        Es. Linux:   ~/.config/devildex
        Es. macOS:
            ~/Library/Application Support/devildex
        Es. Windows:
            C:\\Users\\<Utente>\\AppData\\Roaming\\DevilDexTeam\\devildex\\Config
        """
        path = Path(self._dirs.user_config_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def user_cache_dir(self) -> Path:
        """Directory per i file di cache specifici dell'utente.

        Es. Linux:   ~/.cache/devildex
        Es. macOS:   ~/Library/Caches/devildex
        Es. Windows: C:\\Users\\<Utente>\\AppData\\Local\\DevilDexTeam\\devildex\\Cache
        """
        path = Path(self._dirs.user_cache_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def user_log_dir(self) -> Path:
        """Directory per i file di log specifici dell'utente.

        Es. Linux:   ~/.local/state/devildex/log (o sotto cache/data)
        Es. macOS:   ~/Library/Logs/devildex
        Es. Windows: C:\\Users\\<Utente>\\AppData\\Local\\DevilDexTeam\\devildex\\Logs
        """
        path = Path(self._dirs.user_log_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # --- Percorsi specifici per DevilDex ---

    @property
    def docsets_base_dir(self) -> Path:
        """Directory base predefinita per i docset generati.

        Solitamente si trova all'interno della user_data_dir.
        """
        path = self.user_data_dir / "docsets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Path:
        """Percorso per il file del database dell'applicazione.

        Potrebbe essere un file SQLite, ad esempio.
        """
        return self.user_data_dir / "devildex.db"

    @property
    def settings_file_path(self) -> Path:
        """Percorso per il file delle impostazioni dell'applicazione."""
        return self.user_config_dir / "settings.toml"


if __name__ == "__main__":
    paths = AppPaths()
    logger.info(f"User Data Directory:     {paths.user_data_dir}")
    logger.info(f"User Config Directory:   {paths.user_config_dir}")
    logger.info(f"User Cache Directory:    {paths.user_cache_dir}")
    logger.info(f"User Log Directory:      {paths.user_log_dir}")
    logger.info(f"Docsets Base Directory:  {paths.docsets_base_dir}")
    logger.info(f"Database Path:           {paths.database_path}")
    logger.info(f"Settings File Path:      {paths.settings_file_path}")
