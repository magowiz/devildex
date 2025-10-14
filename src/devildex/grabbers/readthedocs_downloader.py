import logging
from pathlib import Path
from typing import TYPE_CHECKING

from devildex.grabbers.abstract_grabber import AbstractGrabber
from devildex.readthedocs.readthedocs_src import download_and_prepare_rtd_source

if TYPE_CHECKING:
    from devildex.orchestrator.build_context import BuildContext

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s"
    )


class ReadTheDocsDownloader(AbstractGrabber):
    def generate_docset(self, source_path: Path, output_path: Path, context: "BuildContext") -> bool:
        # The download_and_prepare_rtd_source function handles cloning and finding the source.
        # The output_path here will be the base_output_dir for the downloaded source.
        # The actual build will be handled by other builders (e.g., SphinxBuilder) later.
        result_path = download_and_prepare_rtd_source(
            project_name=context.project_slug,
            project_url=context.project_url, # Assuming project_url is available in BuildContext
            existing_clone_path=str(source_path) if source_path.exists() else None,
            output_dir=output_path,
            clone_base_dir_override=output_path.parent # Use parent of output_path as base for clones
        )
        return bool(result_path)

    def can_handle(self, source_path: Path, context: "BuildContext") -> bool:
        # For ReadTheDocsDownloader, we assume it can handle if the project_url is a RTD URL
        # or if the source_path contains a .readthedocs.yaml file.
        # This is a placeholder, more robust detection might be needed.
        if context.project_url and "readthedocs.org" in context.project_url:
            return True
        # Check for .readthedocs.yaml or similar indicator in source_path
        if (source_path / ".readthedocs.yaml").exists():
            return True
        return False
