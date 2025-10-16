import logging
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from devildex.grabbers.abstract_grabber import AbstractGrabber
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import install_project_and_dependencies_in_venv, execute_command

if TYPE_CHECKING:
    from devildex.orchestrator.context import BuildContext

logger = logging.getLogger(__name__)


class Pdoc3Builder(AbstractGrabber):
    """A grabber for generating documentation using pdoc3."""

    BUILDER_NAME = "pdoc3"

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        self.template_dir = template_dir

    def can_handle(self, source_path: Path, context: "BuildContext") -> bool:
        """Determines if this grabber can handle the given project.

        For pdoc3, we check if there are any Python files in the source_path
        and if a Python package root can be resolved.
        """
        if not source_path.is_dir():
            return False

        # Check for presence of Python files
        if not any(source_path.rglob("*.py")):
            return False

        # Check if a Python package root can be resolved
        package_root = context.resolve_package_source_path(context.project_name)
        if not package_root:
            logger.debug(f"Pdoc3Builder: Could not resolve Python package root for {source_path}")
            return False

        return True

    def generate_docset(
        self, source_path: Path, output_path: Path, context: "BuildContext"
    ) -> bool:
        """Generates documentation using pdoc3.

        :param source_path: The path to the source code.
        :param output_path: The path where the documentation should be generated.
        :param context: The build context containing necessary information
            for the build process.
        :return: True if documentation generation was successful, False otherwise.
        """
        logger.info(f"Attempting to generate pdoc3 documentation for {source_path}")

        venv_manager = IsolatedVenvManager(context.temp_dir / "pdoc3_venv")
        try:
            venv_manager.create_venv()
            install_project_and_dependencies_in_venv(
                venv_manager, source_path, context.project_name
            )
            # Install pdoc3
            execute_command(
                [venv_manager.pip_path, "install", "pdoc3"],
                cwd=venv_manager.venv_path,
                description="Installing pdoc3 in isolated venv",
            )

            package_root = context.resolve_package_source_path(context.project_name)
            if not package_root:
                logger.error("Pdoc3Builder: Could not resolve Python package root for pdoc3 generation.")
                return False

            # pdoc3 needs the parent directory of the package in PYTHONPATH
            # and the package name itself as the argument.
            # Example: if package_root is /path/to/project/my_package,
            # then PYTHONPATH should include /path/to/project
            # and the argument to pdoc3 should be my_package
            pythonpath_parent = package_root.parent
            package_name = package_root.name

            # Ensure output directory exists
            output_path.mkdir(parents=True, exist_ok=True)

            pdoc_command = [
                venv_manager.python_path,
                "-m",
                "pdoc",
                "--html",
                "--output-dir",
                str(output_path),
            ]

            if self.template_dir:
                pdoc_command.extend(["--template-dir", str(self.template_dir)])

            pdoc_command.append(package_name)

            env = {"PYTHONPATH": str(pythonpath_parent)}

            result = execute_command(
                pdoc_command,
                cwd=pythonpath_parent, # pdoc3 should be run from the parent of the package
                env=env,
                description=f"Generating pdoc3 documentation for {package_name}",
            )

            if result.returncode != 0:
                logger.error(f"pdoc3 documentation generation failed: {result.stderr}")
                return False

            # Basic validation: check if any HTML files were created
            if not any(output_path.rglob("*.html")):
                logger.error(f"No HTML files found in {output_path} after pdoc3 generation.")
                return False

            logger.info(f"pdoc3 documentation successfully generated in {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error during pdoc3 documentation generation: {e}")
            return False
        finally:
            venv_manager.cleanup_venv()