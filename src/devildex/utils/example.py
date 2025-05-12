"""example context manager venv."""


from devildex.utils.venv_cm import IsolatedVenvManager


project_name = "mio_progetto"
try:
    with IsolatedVenvManager(project_name=project_name) as venv_manager:
        print(f"Usando Python da: {venv_manager.python_executable}")
        print(f"Usando pip da: {venv_manager.pip_executable}")

    print(f"Ambiente virtuale per {project_name} rimosso.")

except Exception as e:
    print(f"Si è verificato un errore: {e}")
