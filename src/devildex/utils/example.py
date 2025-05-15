"""example context manager venv."""

from devildex.utils.venv_cm import IsolatedVenvManager

PROJECT_NAME = "mio_progetto"

with IsolatedVenvManager(project_name=PROJECT_NAME) as venv_manager:
    print(f"Usando Python da: {venv_manager.python_executable}")
    print(f"Usando pip da: {venv_manager.pip_executable}")

print(f"Ambiente virtuale per {PROJECT_NAME} rimosso.")
