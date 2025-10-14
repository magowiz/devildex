from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devildex.orchestrator.build_context import BuildContext


class AbstractGrabber(ABC):
    @abstractmethod
    def generate_docset(self, source_path: Path, output_path: Path, context: "BuildContext") -> bool:
        """
        Abstract method to generate documentation.
        :param source_path: The path to the source code.
        :param output_path: The path where the documentation should be generated.
        :param context: The build context containing necessary information for the build process.
        :return: True if documentation generation was successful, False otherwise.
        """
        pass

    @abstractmethod
    def can_handle(self, source_path: Path, context: "BuildContext") -> bool:
        """
        Abstract method to determine if the grabber can handle a given project.
        :param source_path: The path to the source code.
        :param context: The build context containing necessary information for the build process.
        :return: True if the grabber can handle the project, False otherwise.
        """
        pass
