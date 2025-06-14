"""venv utilities module."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

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
        *packages_list,
    ]
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
    """Check if standard project installation files exist."""
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
        else:
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
            "w",
            encoding="utf-8",
        ) as req_file:
            for line in filtered_req_lines:
                req_file.write(f"{line}\n")
        logger.info(
            "Overwrote '%s' with filtered requirements for installation.",
            doc_requirements_path,
        )
    except OSError:
        logger.exception(
            "Failed to write filtered requirements to '%s'. Skipping install.",
            doc_requirements_path,
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
    """Install the project and/or its dependencies in the Venv provided."""
    if base_packages_to_install is None:
        effective_base_packages = ["sphinx"]
    else:
        effective_base_packages = base_packages_to_install
    return (
        _install_base_packages_in_venv(
            pip_executable, project_name, effective_base_packages
        )
        and _install_project_editable_in_venv(
            pip_executable, project_name, project_root_for_install
        )
        and _install_doc_requirements_in_venv(
            pip_executable, project_name, doc_requirements_path
        )
    )


def _prepare_command_env(
    base_env: dict[str, str], additional_env: dict[str, str] | None
) -> dict[str, str]:
    """Prepare the environment dictionary for subprocess."""
    current_env = base_env.copy()
    if additional_env:
        current_env.update(additional_env)
    return current_env


def _log_command_failure_details(
    description: str, return_code: int, stdout_text: str | None, stderr_text: str | None
) -> None:
    """Log details and prints debug info for a failed command."""
    logger.warning("%s failed. Return code: %s", description, return_code)
    if stdout_text and stdout_text.strip():
        logger.debug("Stdout:\n%s", stdout_text.strip())
    if stderr_text and stderr_text.strip():
        stripped_stderr = stderr_text.strip()
        logger.debug("Stderr:\n%s", stripped_stderr)
        logger.debug(
            f"DEBUG STDERR from FAILED command '{description}':" f"\n{stripped_stderr}"
        )


def _log_command_success_details(
    description: str, stdout_text: str | None, stderr_text: str | None
) -> None:
    """Log details for a successfully executed command."""
    logger.info("%s completed successfully.", description)
    if stdout_text and stdout_text.strip():
        logger.debug("Stdout (success):\n%s", stdout_text.strip())
    if stderr_text and stderr_text.strip():
        logger.debug("Stderr (success/warnings):\n%s", stderr_text.strip())


def _log_sphinx_specific_debug(
    description: str, stdout_text: str | None, stderr_text: str | None
) -> None:
    """Print Sphinx-specific debug STDOUT and STDERR if applicable."""
    if "sphinx" in description.lower():
        actual_stdout = stdout_text.strip() if stdout_text else "<empty>"
        actual_stderr = stderr_text.strip() if stderr_text else "<empty>"
        logger.debug(f"DEBUG SPHINX STDOUT for '{description}':\n{actual_stdout}")
        logger.debug(f"DEBUG SPHINX STDERR for '{description}':\n{actual_stderr}")


def _get_effective_cwd(cwd_param: str | None) -> str:
    """Return the CWD string to use for logging, defaulting to '.'."""
    return cwd_param or "."


def _handle_command_result(
    process: subprocess.CompletedProcess,
    command: list[str],
    description: str,
    cwd_param: str | None,
) -> int:
    """Manage the result of the subprocess, logga and printing of debug info."""
    full_command_str = " ".join(command)
    effective_cwd = _get_effective_cwd(cwd_param)

    logger.debug(f"DEBUG EXEC_CMD: Preparing to execute command[0]: {command[0]}")
    logger.debug(f"DEBUG EXEC_CMD: Full command list: {command}")
    logger.debug(f"DEBUG EXEC_CMD: Working directory (cwd): {effective_cwd}")

    logger.info("Executing: %s (cwd: %s)", full_command_str, effective_cwd)

    _log_sphinx_specific_debug(description, process.stdout, process.stderr)

    if process.returncode != 0:
        _log_command_failure_details(
            description, process.returncode, process.stdout, process.stderr
        )
    else:
        _log_command_success_details(description, process.stdout, process.stderr)

    return process.returncode


def execute_command(
    command: list[str],
    description: str,
    cwd: str | Path | None = None,
    env: Optional[dict] = None,
) -> tuple[str, str, int]:
    """Execute a command of shell and returns stdout, stderr and return code."""
    if not command:
        return "", "empty command list", -1
    cwd_str = str(cwd) if cwd else None
    command_str_for_log = " ".join(command)
    try:
        current_env = _prepare_command_env(os.environ.copy(), env)
        process = subprocess.run(  # noqa: S603
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

    except FileNotFoundError:
        logger.exception(
            "Command not found: %s. Ensure it's in PATH or provide full path.",
            (command[0] if command else "N/A"),
        )

        return "", f"Command not found: {command[0] if command else 'N/A'}", -1

    except PermissionError as e:
        logger.exception(
            "Permission denied during command execution '%s'",
            command_str_for_log,
        )

        return "", f"Permission denied: {e}", -3

    except OSError as e:
        logger.exception("OS error during command execution '%s'", command_str_for_log)

        return "", f"OS error: {e}", -4

    except ValueError as e:
        logger.exception(
            "Value error during command setup or execution for '%s'",
            command_str_for_log,
        )

        return "", f"Value error: {e}", -5
    else:
        return process.stdout, process.stderr, ret_code


def _install_common_project_requirements(
    pip_executable: str, project_root: Path, project_name: str
) -> bool:
    """Check for and installs from common project-specific requirements files."""
    logger.info(
        "Searching for common project requirements files for '%s' in %s...",
        project_name,
        project_root,
    )
    potential_req_files_relative = [
        "requirements.txt",
        "docs/requirements.txt",
        "doc/requirements.txt",
        "requirements/docs.txt",
        "requirements/doc.txt",
        "requirements-docs.txt",
        "dev-requirements.txt",
    ]
    all_installations_successful = True
    found_any_req_file = False

    for req_file_rel_path in potential_req_files_relative:
        req_file_abs_path = project_root / req_file_rel_path
        if req_file_abs_path.is_file():
            found_any_req_file = True
            logger.info(
                "Found project-specific requirements file for '%s': %s",
                project_name,
                req_file_abs_path,
            )
            pip_command_reqs = [
                pip_executable,
                "install",
                "--disable-pip-version-check",
                "--no-python-version-warning",
                "-r",
                str(req_file_abs_path),
            ]
            stdout_req, stderr_req, return_code_reqs = execute_command(
                pip_command_reqs,
                f"Install project requirements from {req_file_abs_path.name} "
                f"for {project_name}",
            )
            if return_code_reqs != 0:
                logger.warning(
                    "Failed to install project-specific requirements from %s for "
                    "'%s'. RC: %s. Stderr: %s",
                    req_file_abs_path,
                    project_name,
                    return_code_reqs,
                    stderr_req.strip(),
                )
                all_installations_successful = False
            else:
                logger.info(
                    "Successfully installed requirements from %s for '%s'.",
                    req_file_abs_path,
                    project_name,
                )
                if stdout_req.strip():
                    logger.debug(
                        "Stdout from requirements install:\n%s", stdout_req.strip()
                    )

    if not found_any_req_file:
        logger.info(
            "No common project-specific requirements files found for '%s' in %s.",
            project_name,
            project_root,
        )
    return all_installations_successful


def install_environment_dependencies(
    pip_executable: str,
    project_name: str,
    project_root_for_install: Path,
    tool_specific_packages: list[str],
    scan_for_project_requirements: bool = True,
    install_project_editable: bool = True,
) -> bool:
    """Install tool-specific packages, common project requirements, and the project."""
    logger.info("Setting up environment for project '%s'...", project_name)

    # 1. Install tool-specific packages (e.g., mkdocs, sphinx, and their plugins)
    if tool_specific_packages:
        logger.info(
            "Installing tool-specific packages for '%s': %s",
            project_name,
            tool_specific_packages,
        )
        if not _install_base_packages_in_venv(  # Re-using this helper
            pip_executable, project_name, tool_specific_packages
        ):
            logger.error(
                "Critical failure: Could not install tool-specific packages for '%s'."
                " Aborting environment setup.",
                project_name,
            )
            return False
    else:
        logger.info(
            "No tool-specific packages provided for '%s'. Skipping this step.",
            project_name,
        )

    # 2. Install common project requirements if requested
    if scan_for_project_requirements:
        logger.info(
            "Scanning for and installing common project requirements for '%s'.",
            project_name,
        )
        if not _install_common_project_requirements(
            pip_executable, project_root_for_install, project_name
        ):
            logger.warning(
                "One or more common project requirements files for '%s' "
                "failed to install. "
                "Build might be affected.",
                project_name,
            )
            # Decide on strictness: for now, this is a warning, not a hard fail.
    else:
        logger.info(
            "Skipping scan for common project requirements for '%s'.", project_name
        )

    # 3. Install the project itself in editable mode if requested and applicable
    if install_project_editable:
        logger.info(
            "Attempting to install project '%s' in editable mode.", project_name
        )
        if not _install_project_editable_in_venv(
            pip_executable, project_name, project_root_for_install
        ):
            logger.warning(
                "Failed to install project '%s' in editable mode. "
                "Build might be affected if project modules are needed by build tools.",
                project_name,
            )
            # Decide on strictness: for now, this is a warning.
    else:
        logger.info("Skipping editable install of project '%s'.", project_name)

    logger.info("Environment setup for project '%s' completed.", project_name)
    return True  # Returns True if critical steps (tool packages) passed.
