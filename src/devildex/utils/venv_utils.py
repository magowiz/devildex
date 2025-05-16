"""venv utilities module."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict

from devildex.utils.deps_utils import filter_requirements_lines

logger = logging.getLogger(__name__)


def _install_base_packages_in_venv(
    pip_executable: str, project_name: str, packages_list: list[str]
) -> bool:
    """Installs a list of base packages into the venv."""
    logger.info(
        "Ensuring base packages (%s) are installed in the venv for '%s'...",
        ", ".join(packages_list),
        project_name,
    )
    install_cmd = [
        pip_executable,
        "install",
        "--disable-pip-version-check",
        "--no-python-version-warning",
    ] + packages_list
    _, _, ret_code = execute_command(
        install_cmd, f"Install/Verify base packages for {project_name}"
    )
    if ret_code != 0:
        logger.error(
            "CRITICAL: Failed to install/verify base packages (%s) in venv for '%s'.",
            ", ".join(packages_list),
            project_name,
        )
        return False
    logger.info(
        "Base packages (%s) installed/verified successfully for '%s'.",
        ", ".join(packages_list),
        project_name,
    )
    return True


def _has_installable_project_files(project_root: Path) -> bool:
    """Checks if standard project installation files exist."""
    return (
        (project_root / "setup.py").exists()
        or (project_root / "setup.cfg").exists()
        or (project_root / "pyproject.toml").exists()
    )


def _install_project_editable_in_venv(
    pip_executable: str, project_name: str, project_root_for_install: Path | None
) -> bool:
    """Installs the project in editable mode if conditions are met."""
    if not project_root_for_install:
        logger.info(
            "No project root for installation provided for '%s'. "
            "Skipping editable install.",
            project_name,
        )
        return True
    if not project_root_for_install.exists():
        logger.info(
            "Project root for installation '%s' does not exist"
            " for '%s'. Skipping editable install.",
            project_root_for_install,
            project_name,
        )
        return True

    if not _has_installable_project_files(project_root_for_install):
        logger.info(
            "No setup.py, setup.cfg, or pyproject.toml found in '%s'. "
            "Skipping editable install of project '%s'.",
            project_root_for_install,
            project_name,
        )
        return True

    logger.info(
        "Attempting to install project '%s' from '%s' "
        "in editable mode into the venv...",
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
            "Project '%s' installed successfully (or already present) "
            "in editable mode in venv.",
            project_name,
        )
        return True
    logger.error(
        "Failed to install project '%s' in editable mode in venv. "
        "Error details in DEBUG log.",
        project_name,
    )
    return False


def _install_doc_requirements_in_venv(
    pip_executable: str, project_name: str, doc_requirements_path: Path | None
) -> bool:
    """Installs documentation-specific requirements if specified and valid."""
    if not doc_requirements_path or not doc_requirements_path.exists():
        if not doc_requirements_path:
            logger.info(
                "No documentation requirements file path provided for %s, "
                "skipping dependency installation.",
                project_name,
            )
        else:  # This means doc_requirements_path was provided but does not exist
            logger.warning(
                "Documentation requirements file not found at '%s', skipping.",
                doc_requirements_path,
            )
        return True

    logger.info(
        "Attempting to install documentation-specific "
        "dependencies from '%s' into the venv...",
        doc_requirements_path,
    )
    logger.info("Attempting to filter requirements file: %s", doc_requirements_path)
    filtered_req_lines = filter_requirements_lines(str(doc_requirements_path))

    if filtered_req_lines is None:
        logger.error(
            "Failed to read or parse requirements file '%s'. "
            "Skipping install of doc dependencies.",
            doc_requirements_path,
        )
        return False

    if not filtered_req_lines:
        logger.info(
            "No valid requirements found in '%s' after filtering. Skipping install.",
            doc_requirements_path,
        )
        return True

    requirements_filename_to_use = doc_requirements_path.name
    try:
        with open(
            doc_requirements_path.parent / requirements_filename_to_use,
            "wt",
            encoding="utf-8",
        ) as req_file:
            for line in filtered_req_lines:
                req_file.write(f"{line}\n")
        logger.info(
            "Overwrote '%s' with filtered requirements for installation.",
            doc_requirements_path,
        )
    except IOError as e:
        logger.error(
            "Failed to write filtered requirements to '%s': %s. Skipping install.",
            doc_requirements_path,
            e,
        )
        return False

    req_install_cmd = [
        pip_executable,
        "install",
        "--disable-pip-version-check",
        "--no-python-version-warning",
        "-r",
        requirements_filename_to_use,
    ]
    _, _, ret_code = execute_command(
        req_install_cmd,
        f"Install doc requirements for {project_name}",
        cwd=doc_requirements_path.parent,
    )
    if ret_code == 0:
        logger.info(
            "Dependencies from '%s' installed successfully "
            "(or already present) in venv.",
            doc_requirements_path,
        )
        return True
    logger.error(
        "Failed to install dependencies from '%s' in venv. Error details in DEBUG log.",
        doc_requirements_path,
    )
    return False


def install_project_and_dependencies_in_venv(
    pip_executable: str,
    project_name: str,
    project_root_for_install: Path | None,
    doc_requirements_path: Path | None,
    base_packages_to_install: list[str] | None = None,
) -> bool:
    """Installa il progetto e/o le sue dipendenze nel venv fornito."""
    if base_packages_to_install is None:
        effective_base_packages = ["sphinx"]
    else:
        effective_base_packages = base_packages_to_install
    if not _install_base_packages_in_venv(
        pip_executable, project_name, effective_base_packages
    ):
        return False
    if not _install_project_editable_in_venv(
        pip_executable, project_name, project_root_for_install
    ):
        return False

    if not _install_doc_requirements_in_venv(
        pip_executable, project_name, doc_requirements_path
    ):
        return False

    return True


def _prepare_command_env(
    base_env: Dict[str, str], additional_env: Dict[str, str] | None
) -> Dict[str, str]:
    """Prepara il dizionario dell'ambiente per il subprocess."""
    current_env = base_env.copy()
    if additional_env:
        current_env.update(additional_env)
    return current_env


def _log_command_failure_details(
    description: str, returncode: int, stdout_text: str | None, stderr_text: str | None
):
    """Logs details and prints debug info for a failed command."""
    logger.warning("%s failed. Return code: %s", description, returncode)
    if stdout_text and stdout_text.strip():
        logger.debug("Stdout:\n%s", stdout_text.strip())
    if stderr_text and stderr_text.strip():
        stripped_stderr = stderr_text.strip()
        logger.debug("Stderr:\n%s", stripped_stderr)
        print(f"DEBUG STDERR from FAILED command '{description}':\n{stripped_stderr}")


def _log_command_success_details(
    description: str, stdout_text: str | None, stderr_text: str | None
):
    """Logs details for a successfully executed command."""
    logger.info("%s completed successfully.", description)
    if stdout_text and stdout_text.strip():
        logger.debug("Stdout (success):\n%s", stdout_text.strip())
    if stderr_text and stderr_text.strip():
        logger.debug("Stderr (success/warnings):\n%s", stderr_text.strip())


def _log_sphinx_specific_debug(
    description: str, stdout_text: str | None, stderr_text: str | None
):
    """Prints Sphinx-specific debug STDOUT and STDERR if applicable."""
    if "sphinx" in description.lower():
        actual_stdout = stdout_text.strip() if stdout_text else "<empty>"
        actual_stderr = stderr_text.strip() if stderr_text else "<empty>"
        print(f"DEBUG SPHINX STDOUT for '{description}':\n{actual_stdout}")
        print(f"DEBUG SPHINX STDERR for '{description}':\n{actual_stderr}")


def _get_effective_cwd(cwd_param: str | None) -> str:
    """Returns the CWD string to use for logging, defaulting to '.'."""
    return cwd_param or "."


def _handle_command_result(
    process: subprocess.CompletedProcess,
    command: list[str],
    description: str,
    cwd_param: str | None,
) -> int:
    """Gestisce il risultato del subprocess, logga e stampa info di debug."""
    full_command_str = " ".join(command)
    effective_cwd = _get_effective_cwd(cwd_param)

    # Initial debug prints
    print(f"DEBUG EXEC_CMD: Preparing to execute command[0]: {command[0]}")
    print(f"DEBUG EXEC_CMD: Full command list: {command}")
    print(f"DEBUG EXEC_CMD: Working directory (cwd): {effective_cwd}")

    logger.info("Executing: %s (cwd: %s)", full_command_str, effective_cwd)

    # Sphinx-specific debug output
    _log_sphinx_specific_debug(description, process.stdout, process.stderr)

    # Handle command result
    if process.returncode != 0:
        _log_command_failure_details(
            description, process.returncode, process.stdout, process.stderr
        )
    else:
        _log_command_success_details(description, process.stdout, process.stderr)

    return process.returncode


def execute_command(
    command: list[str], description: str, cwd: str | Path | None = None, env=None
) -> tuple[str, str, int]:
    """Esegue un comando di shell e restituisce stdout, stderr e return code."""
    cwd_str = str(cwd) if cwd else None
    command_str_for_log = " ".join(
        command
    )
    try:
        current_env = _prepare_command_env(os.environ.copy(), env)

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

        ret_code = _handle_command_result(process, command, description, cwd_str)

        return process.stdout, process.stderr, ret_code

    except FileNotFoundError:

        logger.error(
            "Command not found: %s. Ensure it's in PATH or provide full path.",
            (
                command[0] if command else "N/A"
            ),
        )

        return "", f"Command not found: {command[0] if command else 'N/A'}", -1

    except PermissionError as e:

        logger.error(
            "Permission denied during command execution '%s': %s",
            command_str_for_log,
            e,
        )

        return "", f"Permission denied: {e}", -3  # New error code for permission issues

    except OSError as e:

        logger.error(
            "OS error during command execution '%s': %s", command_str_for_log, e
        )

        return "", f"OS error: {e}", -4

    except ValueError as e:
        logger.error(
            "Value error during command setup or execution for '%s': %s",
            command_str_for_log,
            e,
        )

        return "", f"Value error: {e}", -5  # New error code for value errors
