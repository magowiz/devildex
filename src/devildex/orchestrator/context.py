"""Module for the build context."""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from devildex.scanner.scanner import _find_python_package_root

logger = logging.getLogger(__name__)


@dataclass
class BuildContext:
    """A context object that holds all state for a documentation build process."""

    project_name: str
    project_version: str
    base_output_dir: Path
    vcs_url: Optional[str] = None

    temp_dir: Path = field(init=False)
    final_docs_dir: Path = field(init=False)

    source_root: Optional[Path] = None

    doc_source_root: Optional[Path] = None
    sphinx_conf_py: Optional[Path] = None
    mkdocs_yml: Optional[Path] = None

    def __post_init__(self) -> None:
        """Initialize calculated paths."""
        self.base_output_dir = self.base_output_dir.resolve()
        self.temp_dir = self.base_output_dir / "_temp"
        self.final_docs_dir = (
            self.base_output_dir / self.project_name / self.project_version
        )

    def setup_directories(self) -> None:
        """Create the necessary base directories, cleaning them if they exist."""
        for dir_path in [self.temp_dir, self.final_docs_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
            dir_path.mkdir(parents=True, exist_ok=True)

    def resolve_package_source_path(self, project_name: str) -> Optional[Path]:
        """Resolve the actual path to the main Python pkg/mod within the source_root.

        This is crucial for docstrings-based documentation tools like pdoc.
        """
        if not self.source_root or not self.source_root.is_dir():
            logger.error("BuildContext: source_root is not set or not a directory.")
            return None

        return _find_python_package_root(self.source_root)
