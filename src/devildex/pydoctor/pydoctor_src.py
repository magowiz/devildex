import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from devildex.orchestrator.context import BuildContext
from devildex.utils import venv_cm, venv_utils

logger = logging.getLogger(__name__)


class PydoctorSrc:
    """Implement class that builds documentation from docstrings using Pydoctor."""

    def __init__(
        self, template_dir: Optional[Path] = None, output_dir: Path | str | None = None
    ) -> None:
        """Initialize PydoctorSrc."""
        self.template_dir = template_dir
        self.output_dir = output_dir
        logger.info("PydoctorSrc initialized.")

    def _build_pydoctor_command(
        self, python_executable: str, context: BuildContext, output_path: Path, module_to_document_name: str
    ) -> list[str]:
        """Constructs the pydoctor command for documentation generation."""
        pydoctor_command = [
            python_executable,
            "-m",
            "pydoctor",
            "--html",
            f"--output={output_path}",
            f"--project-name={context.project_name}",
        ]
        if context.vcs_url:
            pydoctor_command.append(f"--project-url={context.vcs_url}")
        if self.template_dir:
            pydoctor_command.append(f"--template-dir={self.template_dir}")

        pydoctor_command.append(module_to_document_name)

        return pydoctor_command

    def generate_docs_from_folder(self, context: BuildContext) -> str | bool:
        """Generate HTML documentation using Pydoctor in an isolated environment."""
        logger.info("PydoctorSrc: Attempting to generate docs for %s", context.project_name)

        # Define the output directory for pydoctor
        if self.output_dir:
            pydoctor_output_dir = Path(self.output_dir) / context.project_name
        else:
            pydoctor_output_dir = (
                context.base_output_dir / context.project_name
            )

        # Clean up existing output directory if it exists
        if pydoctor_output_dir.exists():
            shutil.rmtree(pydoctor_output_dir)
        pydoctor_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "PydoctorSrc: Final output directory for this project: %s",
            pydoctor_output_dir,
        )

        # Create a temporary virtual environment
        with venv_cm.create_venv(context.project_name) as venv_executables:
            python_executable = venv_executables.python_executable
            pip_executable = venv_executables.pip_executable

            # Install pydoctor and sphinxarg (for pydoctor's own docs)
            base_packages = ["pydoctor", "sphinxarg"]
            install_config = venv_utils.InstallConfig(
                project_root_for_install=context.project_install_root,
                tool_specific_packages=base_packages,
                scan_for_project_requirements=True,
                install_project_editable=True,
            )

            if not venv_utils.install_environment_dependencies(
                pip_executable, context.project_name, install_config
            ):
                logger.error(
                    "PydoctorSrc: CRITICAL: Failed to install pydoctor or project "
                    "dependencies for %s in venv. Aborting pydoctor build.",
                    context.project_name,
                )
                return False

            # Construct the pydoctor command
            # The cwd for pydoctor should be the parent of the package/module being documented.
            # The argument to pydoctor should be the name of the package/module.
            pydoctor_cwd = context.project_install_root.parent
            module_to_document_name = context.project_install_root.name

            pydoctor_command = self._build_pydoctor_command(
                python_executable, context, pydoctor_output_dir, module_to_document_name
            )

            logger.info(
                "PydoctorSrc: Executing pydoctor command: %s (cwd: %s)",
                " ".join(pydoctor_command),
                pydoctor_cwd,
            )

            # Execute the pydoctor command
            stdout, stderr, return_code = venv_utils.execute_command(
                pydoctor_command,
                f"Pydoctor build for {context.project_name}",
                cwd=pydoctor_cwd,
            )

            if return_code != 0:
                logger.error(
                    "PydoctorSrc: Pydoctor build failed for %s. Return Code: %s",
                    context.project_name,
                    return_code,
                )
                logger.error("Pydoctor Stdout:\n%s", stdout)
                logger.error("Pydoctor Stderr:\n%s", stderr)
                return False
            else:
                logger.info(
                    "PydoctorSrc: Pydoctor build for %s completed successfully.",
                    context.project_name,
                )
                return str(pydoctor_output_dir)
