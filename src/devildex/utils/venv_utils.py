import os
import subprocess
import logging  # Aggiungi questo
from pathlib import Path

# Rimuovi l'import di _execute_command e logger da readthedocs_src
from devildex.utils.deps_utils import filter_requirements_lines

logger = logging.getLogger(__name__)  # Logger specifico per questo modulo


def install_project_and_dependencies_in_venv(
    pip_executable: str,  # Pip dell'ambiente isolato
    project_name: str,
    project_root_for_install: (
        Path | None
    ),  # Path alla radice del progetto per 'pip install -e .'
    doc_requirements_path: (
        Path | None
    ),  # Path completo al file requirements.txt per i docs
    base_packages_to_install=None,
) -> bool:
    """Installa il progetto e/o le sue dipendenze nel venv fornito."""
    if base_packages_to_install is None:
        base_packages_to_install = ["sphinx"]
    success = True
    logger.info(f"Ensuring Sphinx is installed in the venv for '{project_name}'...")
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
            f"CRITICAL: Failed to install/verify Sphinx in venv for '{project_name}'. Sphinx build will fail."
        )
        # Non impostare overall_install_success = False qui, restituisci direttamente False
        return False  # Fallimento critico, impossibile procedere

    # Installare il progetto stesso in modalità editable, se specificato
    if project_root_for_install and project_root_for_install.exists():
        # Verifica la presenza di setup.py, setup.cfg o pyproject.toml per decidere se installare
        if not (
            (project_root_for_install / "setup.py").exists()
            or (project_root_for_install / "setup.cfg").exists()
            or (project_root_for_install / "pyproject.toml").exists()
        ):
            logger.info(
                f"No setup.py, setup.cfg, or pyproject.toml found in '{project_root_for_install}'. Skipping editable install of project '{project_name}'."
            )
        else:
            logger.info(
                f"Attempting to install project '{project_name}' from '{project_root_for_install}' in editable mode into the venv..."
            )
            install_cmd = [
                pip_executable,
                "install",
                "--disable-pip-version-check",
                "--no-python-version-warning",
                "-e",
                ".",
            ]
            # Esegui pip dalla radice del progetto
            pip_stdout, pip_stderr, ret_code = execute_command(
                install_cmd,
                f"Editable install of {project_name}",
                cwd=project_root_for_install,  # Usa Path object direttamente
            )
            if ret_code == 0:
                logger.info(
                    f"Project '{project_name}' installed successfully (or already present) in venv."
                )
            else:
                logger.error(
                    f"Failed to install project '{project_name}' in venv. Error details in DEBUG log."
                )
                success = False  # Potresti voler interrompere qui
    else:
        logger.info(
            f"No project root provided for installation, or path does not exist. Skipping editable install of project '{project_name}'."
        )

    # Installare le dipendenze specifiche della documentazione, se specificate
    if doc_requirements_path and doc_requirements_path.exists():
        logger.info(
            f"Attempting to install documentation-specific dependencies from '{doc_requirements_path}' into the venv..."
        )
        logger.info(f"Attempting to filter requirements file: {doc_requirements_path}")
        filtered_req_lines = filter_requirements_lines(str(doc_requirements_path))

        # Esegui pip dalla cartella del requirements.txt o dalla radice del progetto
        requirements_filename = doc_requirements_path.name
        if filtered_req_lines:
            with open(
                doc_requirements_path.parent / requirements_filename, "wt"
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
        pip_stdout, pip_stderr, ret_code = execute_command(
            req_install_cmd,
            f"Install doc requirements for {project_name}",
            cwd=doc_requirements_path.parent,  # Usa Path object
        )
        if ret_code == 0:
            logger.info(
                f"Dependencies from '{doc_requirements_path}' installed successfully (or already present) in venv."
            )
        else:
            logger.error(
                f"Failed to install dependencies from '{doc_requirements_path}' in venv. Error details in DEBUG log."
            )
            success = False
    elif doc_requirements_path:  # Se il path era fornito ma non esiste
        logger.warning(
            f"Documentation requirements file not found at '{doc_requirements_path}', skipping."
        )
    else:
        logger.info(
            f"No documentation requirements file provided for {project_name}, skipping dependency installation."
        )
    return success


def execute_command(
    command: list[str], description: str, cwd: str | Path | None = None, env=None
) -> tuple[str, str, int]:
    """Esegue un comando di shell e restituisce stdout, stderr e return code."""
    try:
        # Assicura che cwd sia una stringa se è un Path
        cwd_str = str(cwd) if cwd else None
        current_env = os.environ.copy()
        if env:
            current_env.update(env)
        print(f"DEBUG EXEC_CMD: Preparing to execute command[0]: {command[0]}")
        print(f"DEBUG EXEC_CMD: Full command list: {command}")
        print(f"DEBUG EXEC_CMD: Working directory (cwd): {cwd_str or '.'}")

        logger.info(f"Executing: {' '.join(command)} (cwd: {cwd_str or '.'})")
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
                f"DEBUG SPHINX STDOUT for '{description}':\n{process.stdout.strip() if process.stdout else '<empty>'}"
            )
            print(
                f"DEBUG SPHINX STDERR for '{description}':\n{process.stderr.strip() if process.stderr else '<empty>'}"
            )

        if process.returncode != 0:
            logger.warning(f"{description} failed. Return code: {process.returncode}")
            # Logga stdout/stderr solo se c'è contenuto e il comando è fallito
            if process.stdout.strip():
                logger.debug(f"Stdout:\n{process.stdout.strip()}")
            if process.stderr.strip():
                logger.debug(f"Stderr:\n{process.stderr.strip()}")
                print(
                    f"DEBUG STDERR from FAILED command '{description}':\n{process.stderr.strip()}"
                )

        else:
            logger.info(f"{description} completed successfully.")
            # Logga stdout/stderr anche in caso di successo se contengono informazioni utili (a livello DEBUG)
            if process.stdout.strip():
                logger.debug(f"Stdout (success):\n{process.stdout.strip()}")
            if process.stderr.strip():  # Spesso i warning di Sphinx finiscono qui
                logger.debug(f"Stderr (success/warnings):\n{process.stderr.strip()}")
        return process.stdout, process.stderr, process.returncode
    except FileNotFoundError:
        logger.error(
            f"Command not found: {command[0]}. Ensure it's in PATH or provide full path."
        )
        return "", f"Command not found: {command[0]}", -1
    except Exception as e:
        logger.error(f"Exception during command execution '{' '.join(command)}': {e}")
        return "", str(e), -2
