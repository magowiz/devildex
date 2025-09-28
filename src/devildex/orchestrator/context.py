"""Module for the build context."""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from devildex.scanner.scanner import _find_python_package_root

logger = logging.getLogger(__name__)

@dataclass
class BuildContext:
    """A mutable, shared context object that holds all state for a documentation build process."""

    # --- Initial, known information ---
    project_name: str
    project_version: str
    base_output_dir: Path
    vcs_url: Optional[str] = None

    # --- Paths determined at initialization ---
    # A single temp directory for all intermediate artifacts
    temp_dir: Path = field(init=False)
    # The final destination for the built documentation
    final_docs_dir: Path = field(init=False)

    # --- Paths and info discovered during the process ---
    # Populated by the fetcher
    source_root: Optional[Path] = None

    # Populated by the scanner/grabber
    doc_source_root: Optional[Path] = None  # e.g., the 'docs/' subdir
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
        import shutil

        for dir_path in [self.temp_dir, self.final_docs_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
            dir_path.mkdir(parents=True, exist_ok=True)

    def resolve_package_source_path(self, project_name: str) -> Optional[Path]:
        """Resolves the actual path to the main Python package/module within the source_root.
        This is crucial for docstrings-based documentation tools like pdoc.
        """
        if not self.source_root or not self.source_root.is_dir():
            logger.error("BuildContext: source_root is not set or not a directory.")
            return None

        return _find_python_package_root(self.source_root)
