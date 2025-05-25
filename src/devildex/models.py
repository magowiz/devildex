# /home/magowiz/MEGA/projects/devildex/src/devildex/models.py
from dataclasses import dataclass, field
from typing import Any, Dict  # Per Python < 3.9, altrimenti puoi usare dict
from pathlib import Path # Se vuoi usare Path come type hint

@dataclass
class PackageDetails:
    """Contiene i dettagli di un pacchetto software."""
    name: str
    version: str
    project_urls: Dict[str, str] = field(default_factory=dict)
    initial_source_path: Path | str | None = None # Percorso del clone iniziale se disponibile
    vcs_url: str | None = None # URL VCS specifico (es. git, hg)
    rtd_url: str | None = None # URL di ReadTheDocs

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageDetails":
        """Crea un'istanza di PackageDetails da un dizionario."""

        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            project_urls=data.get("project_urls", {}),
            initial_source_path=data.get("initial_source_path"),
            vcs_url=data.get("vcs_url"),
            rtd_url=data.get("rtd_url")
        )