from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass
class PackageDetails:
    """Contiene i dettagli di un pacchetto software."""

    name: str
    version: str
    project_urls: Dict[str, str] = field(default_factory=dict)
    initial_source_path: Path | str | None = (
        None
    )
    vcs_url: str | None = None
    rtd_url: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageDetails":
        """Crea un'istanza di PackageDetails da un dizionario."""

        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            project_urls=data.get("project_urls", {}),
            initial_source_path=data.get("initial_source_path"),
            vcs_url=data.get("vcs_url"),
            rtd_url=data.get("rtd_url"),
        )
