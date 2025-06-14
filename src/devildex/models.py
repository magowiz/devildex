"""models module."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PackageDetails:
    """Contains details of a  software package."""

    name: str
    version: str
    project_urls: dict[str, str] = field(default_factory=dict)
    initial_source_path: Path | str | None = None
    vcs_url: str | None = None
    rtd_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackageDetails":
        """Create an istance of PackageDetails from a dictionary."""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            project_urls=data.get("project_urls", {}),
            initial_source_path=data.get("initial_source_path"),
            vcs_url=data.get("vcs_url"),
            rtd_url=data.get("rtd_url"),
        )
