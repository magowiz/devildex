from pathlib import Path
# Assumendo che IsolatedVenvManager sia in devildex.utils.venv_cm
from devildex.utils.venv_cm import IsolatedVenvManager

# ... altro codice ...

project_name = "mio_progetto"
try:
    with IsolatedVenvManager(project_name=project_name) as venv_manager:
        # Ora sei dentro un ambiente virtuale temporaneo e isolato
        print(f"Usando Python da: {venv_manager.python_executable}")
        print(f"Usando pip da: {venv_manager.pip_executable}")

        # Qui puoi eseguire comandi pip o script python usando
        # venv_manager.pip_executable e venv_manager.python_executable
        # Esempio:
        # subprocess.run([venv_manager.pip_executable, "install", "requests"], check=True)
        # subprocess.run([venv_manager.python_executable, "mio_script.py"], check=True)

    # Uscendo dal blocco 'with', il venv temporaneo viene automaticamente rimosso
    print(f"Ambiente virtuale per {project_name} rimosso.")

except Exception as e:
    print(f"Si è verificato un errore: {e}")
