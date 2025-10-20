"""Pdoc3 Builder module."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from devildex.grabbers.abstract_grabber import AbstractGrabber
from devildex.utils.venv_cm import IsolatedVenvManager
from devildex.utils.venv_utils import (
    execute_command,
    install_project_and_dependencies_in_venv,
)

if TYPE_CHECKING:
    from devildex.orchestrator.context import BuildContext

logger = logging.getLogger(__name__)


class Pdoc3Builder(AbstractGrabber):
    """A grabber for generating documentation using pdoc3."""

    BUILDER_NAME = "pdoc3"

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        """Initialize the Pdoc3Builder."""
        self.template_dir = template_dir

    def can_handle(self, source_path: Path, context: "BuildContext") -> bool:
        """Determine if this grabber can handle the given project."""
        if not source_path.is_dir():
            return False

        # Check for presence of Python files
        if not any(source_path.rglob("*.py")):
            return False

        # Check if a Python package root can be resolved
        package_root = context.resolve_package_source_path(context.project_name)
        if not package_root:
            logger.debug(
                f"Pdoc3Builder: Could not resolve Python package root for "
                f"{source_path}"
            )
            return False

        return True

    def generate_docset(
        self, source_path: Path, output_path: Path, context: "BuildContext"
    ) -> bool:
        """Generate documentation using pdoc3."""
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
                logger.error(
                    "Pdoc3Builder: Could not resolve Python package root for "
                    "pdoc3 generation."
                )
                return False

            pythonpath_parent = package_root.parent
            package_name = package_root.name
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

            stdout, stderr, returncode = execute_command(
                pdoc_command,
                cwd=pythonpath_parent,
                env=env,
                description=f"Generating pdoc3 documentation for {package_name}",
            )

            if returncode != 0:
                logger.error(f"pdoc3 documentation generation failed: {stderr}")
                return False

            if not any(output_path.rglob("*.html")):
                logger.error(
                    f"No HTML files found in {output_path} after pdoc3 generation."
                )
                return False
            else:
                logger.info(
                    f"pdoc3 documentation successfully generated in {output_path}"
                )
                return True

        except Exception:
            logger.exception("Error during pdoc3 documentation generation")
            return False
        finally:
            venv_manager.cleanup_venv()
