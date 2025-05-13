"""venv utilities module."""

import logging
import os
import subprocess
from pathlib import Path

from devildex.utils.deps_utils import filter_requirements_lines

logger = logging.getLogger(__name__)


def install_project_and_dependencies_in_venv(
    pip_executable: str,
    project_name: str,
    project_root_for_install: Path | None,
    doc_requirements_path: Path | None,
    base_packages_to_install=None,
) -> bool:
    """Installa il progetto e/o le sue dipendenze nel venv fornito."""
    if base_packages_to_install is None:
        base_packages_to_install = ["sphinx"]
    success = True
    logger.info("Ensuring Sphinx is installed in the venv for '%s'...", project_name)
    sphinx_install_cmd = [
        pip_executable,
        "install",
        "--disable-pip-version-check",
        "--no-python-version-warning",
    ] + base_packages_to_install
    _, _, ret_code_sphinx = execute_command(
        sphinx_install_cmd, f"Install/Verify Sphinx for {project_name}"
    )
    if ret_code_sphinx != 0:
        logger.error(
            "CRITICAL: Failed to install/verify Sphinx in venv for "
            "'%s'. Sphinx build will fail.",
            project_name,
        )
        return False

    if project_root_for_install and project_root_for_install.exists():
        if not (
            (project_root_for_install / "setup.py").exists()
            or (project_root_for_install / "setup.cfg").exists()
            or (project_root_for_install / "pyproject.toml").exists()
        ):
            logger.info(
                "No setup.py, setup.cfg, or pyproject.toml found in "
                "'%s'. Skipping editable install of "
                "project '%s'.",
                project_root_for_install,
                project_name,
            )
        else:
            logger.info(
                "Attempting to install project '%s' from "
                "'%s' in editable mode into the venv...",
                project_name,
                project_root_for_install,
            )
            install_cmd = [
                pip_executable,
                "install",
                "--disable-pip-version-check",
                "--no-python-version-warning",
                "-e",
                ".",
            ]
            _, _, ret_code = execute_command(
                install_cmd,
                f"Editable install of {project_name}",
                cwd=project_root_for_install,
            )
            if ret_code == 0:
                logger.info(
                    "Project '%s' installed successfully (or already present) in venv.",
                    project_name,
                )
            else:
                logger.error(
                    "Failed to install project '%s' in venv. "
                    "Error details in DEBUG log.",
                    project_name,
                )
                success = False
    else:
        logger.info(
            "No project root provided for installation, or path does not exist. "
            "Skipping editable install of project '%s'.",
            project_name,
        )

    if doc_requirements_path and doc_requirements_path.exists():
        logger.info(
            "Attempting to install documentation-specific dependencies from "
            "'%s' into the venv...",
            doc_requirements_path,
        )
        logger.info("Attempting to filter requirements file: %s", doc_requirements_path)
        filtered_req_lines = filter_requirements_lines(str(doc_requirements_path))

        requirements_filename = doc_requirements_path.name
        if filtered_req_lines:
            with open(
                doc_requirements_path.parent / requirements_filename,
                "wt",
                encoding="utf-8",
            ) as req_file:
                for line in filtered_req_lines:
                    req_file.write(f"{line}\n")

        req_install_cmd = [
            pip_executable,
            "install",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "-r",
            requirements_filename,
        ]
        _, _, ret_code = execute_command(
            req_install_cmd,
            f"Install doc requirements for {project_name}",
            cwd=doc_requirements_path.parent,
        )
        if ret_code == 0:
            logger.info(
                "Dependencies from '%s' installed "
                "successfully (or already present) in venv.",
                doc_requirements_path,
            )
        else:
            logger.error(
                "Failed to install dependencies from '%s' "
                "in venv. Error details in DEBUG log.",
                doc_requirements_path,
            )
            success = False
    elif doc_requirements_path:  # Se il path era fornito ma non esiste
        logger.warning(
            "Documentation requirements file not found at '%s', skipping.",
            doc_requirements_path,
        )
    else:
        logger.info(
            "No documentation requirements file provided for %s, "
            "skipping dependency installation.",
            project_name,
        )
    return success


def execute_command(
    command: list[str], description: str, cwd: str | Path | None = None, env=None
) -> tuple[str, str, int]:
    """Esegue un comando di shell e restituisce stdout, stderr e return code."""
    try:
        cwd_str = str(cwd) if cwd else None
        current_env = os.environ.copy()
        if env:
            current_env.update(env)
        print(f"DEBUG EXEC_CMD: Preparing to execute command[0]: {command[0]}")
        print(f"DEBUG EXEC_CMD: Full command list: {command}")
        print(f"DEBUG EXEC_CMD: Working directory (cwd): {cwd_str or '.'}")

        logger.info("Executing: %s (cwd: %s)", " ".join(command), cwd_str or ".")
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=cwd_str,
            encoding="utf-8",
            errors="replace",
            env=current_env,
        )
        if "sphinx" in description.lower():
            print(
                "DEBUG SPHINX STDOUT for "
                f"'{description}':\n{process.stdout.strip() if process.stdout else '<empty>'}"
            )
            print(
                "DEBUG SPHINX STDERR for "
                f"'{description}':\n"
                f"{process.stderr.strip() if process.stderr else '<empty>'}"
            )

        if process.returncode != 0:
            logger.warning(
                "%s failed. Return code: %s", description, process.returncode
            )
            if process.stdout.strip():
                logger.debug("Stdout:\n%s", process.stdout.strip())
            if process.stderr.strip():
                logger.debug("Stderr:\n%s", process.stderr.strip())
                print(
                    f"DEBUG STDERR from FAILED command '{description}':\n"
                    f"{process.stderr.strip()}"
                )

        else:
            logger.info("%s completed successfully.", description)
            if process.stdout.strip():
                logger.debug("Stdout (success):\n%s", process.stdout.strip())
            if process.stderr.strip():
                logger.debug("Stderr (success/warnings):\n%s", process.stderr.strip())
        return process.stdout, process.stderr, process.returncode
    except FileNotFoundError:
        logger.error(
            "Command not found: %s. Ensure it's in PATH or provide full path.",
            command[0],
        )
        return "", f"Command not found: {command[0]}", -1
    except Exception as e:
        logger.error(
            "Exception during command execution '%s': %s", " ".join(command), e
        )
        return "", str(e), -2
