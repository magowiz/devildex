"""PydoctorSrc module."""

import logging
import shutil
from pathlib import Path
from typing import Optional

from devildex.grabbers.abstract_grabber import AbstractGrabber
from devildex.orchestrator.context import BuildContext
from devildex.utils import venv_cm, venv_utils

logger = logging.getLogger(__name__)


class PydoctorBuilder(AbstractGrabber):
    """Implement class that builds documentation from docstrings using Pydoctor."""

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        """Initialize PydoctorBuilder."""
        super().__init__()
        self.template_dir = template_dir
        logger.info("PydoctorBuilder initialized.")

    def _build_pydoctor_command(
        self,
        python_executable: str,
        context: BuildContext,
        output_path: Path,
        module_to_document_name: str,
    ) -> list[str]:
        """Construct the pydoctor command for documentation generation."""
        pydoctor_command = [
            python_executable,
            "-m",
            "pydoctor",
            f"--html-output={output_path}",
            f"--project-name={context.project_name}",
        ]
        if context.vcs_url:
            pydoctor_command.append(f"--project-url={context.vcs_url}")
        if self.template_dir:
            pydoctor_command.append(f"--template-dir={self.template_dir}")

        pydoctor_command.append(module_to_document_name)

        return pydoctor_command

    def generate_docset(
        self, source_path: Path, output_path: Path, context: BuildContext
    ) -> bool:
        """Generate HTML documentation using Pydoctor in an isolated environment."""
        logger.info(
            "PydoctorBuilder: Attempting to generate docs for %s", context.project_name
        )

        pydoctor_output_dir = output_path / context.project_name

        if pydoctor_output_dir.exists():
            shutil.rmtree(pydoctor_output_dir)
        pydoctor_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "PydoctorBuilder: Final output directory for this project: %s",
            pydoctor_output_dir,
        )

        with venv_cm.IsolatedVenvManager(project_name=context.project_name) as i_venv:
            python_executable = i_venv.python_executable
            pip_executable = i_venv.pip_executable

            base_packages = ["pydoctor"]
            install_config = venv_utils.InstallConfig(
                project_root_for_install=source_path,
                tool_specific_packages=base_packages,
                scan_for_project_requirements=True,
                install_project_editable=True,
            )

            if not venv_utils.install_environment_dependencies(
                pip_executable, context.project_name, install_config
            ):
                logger.error(
                    "PydoctorBuilder: CRITICAL: Failed to install pydoctor or project "
                    "dependencies for %s in venv. Aborting pydoctor build.",
                    context.project_name,
                )
                return False

            pydoctor_cwd = source_path.parent
            module_to_document_name = source_path.name

            pydoctor_command = self._build_pydoctor_command(
                python_executable, context, pydoctor_output_dir, module_to_document_name
            )

            logger.info(
                "PydoctorBuilder: Executing pydoctor command: %s (cwd: %s)",
                " ".join(pydoctor_command),
                pydoctor_cwd,
            )

            stdout, stderr, return_code = venv_utils.execute_command(
                pydoctor_command,
                f"Pydoctor build for {context.project_name}",
                cwd=pydoctor_cwd,
            )

            if return_code != 0:
                logger.error(
                    "PydoctorBuilder: Pydoctor build failed for %s. Return Code: %s",
                    context.project_name,
                    return_code,
                )
                logger.error("Pydoctor Stdout:\n%s", stdout)
                logger.error("Pydoctor Stderr:\n%s", stderr)
                return False
            else:
                logger.info(
                    "PydoctorBuilder: Pydoctor build for %s completed successfully.",
                    context.project_name,
                )
                return True

    def can_handle(self, source_path: Path, context: BuildContext) -> bool:
        """Determine if the grabber can handle a given project."""
        pydoctor_conf_path = source_path / "pydoctor.conf"
        if pydoctor_conf_path.is_file():
            logger.info(
                "PydoctorBuilder: Found pydoctor.conf at "
                f"{pydoctor_conf_path}. Can handle."
            )
            return True
        setup_py_path = source_path / "setup.py"
        if setup_py_path.is_file():
            try:
                content = setup_py_path.read_text()
                if "pydoctor" in content:
                    logger.info(
                        "PydoctorBuilder: Found 'pydoctor' in setup.py at"
                        f" {setup_py_path}. Can handle."
                    )
                    return True
            except Exception as e:
                logger.warning(
                    f"PydoctorBuilder: Error reading setup.py at {setup_py_path}: {e}"
                )

        logger.info(
            "PydoctorBuilder: No pydoctor.conf or pydoctor mention in setup.py at"
            f" {source_path}. Cannot handle."
        )
        return False
