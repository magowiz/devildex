import sys
from cx_Freeze import setup, Executable

# Opzioni per la build. Diciamo a cx_Freeze di includere PySide6.
# cx_Freeze di solito le rileva automaticamente, ma è buona pratica specificare le principali.
build_exe_options = {
    "packages": ["pyside6"], # Diciamo a cx_Freeze di includere il pacchetto pyside6 e le sue dipendenze Qt
    # "excludes": ["tkinter", "unittest"], # Puoi escludere librerie standard se non ti servono per ridurre le dimensioni
    # "include_files": [("path/to/data_files", "data")], # Se avessi file di dati (immagini, config), li includeresti qui
    "optimize": 1, # Esempio di ottimizzazione
}

# Definiamo il base dell'eseguibile. Per applicazioni GUI.
# base = None # Default per applicazioni CLI o GUI su Linux
base = "Win32GUI" if sys.platform == "win32" else None # Usa Win32GUI base solo su Windows

# Definiamo gli eseguibili da creare
executables = [
    # Eseguibile che parte dal tuo script minimale
    Executable("minimal_app.py", # Il tuo script principale
               base=base,
               target_name="devildex_app") # Nome del file eseguibile finale
]

# Chiamiamo la funzione setup di cx_Freeze
setup(
    name="devildex", # Nome del progetto
    version="0.1.0", # Versione del progetto
    description="DevilDex Documentation Viewer (Build Test)", # Descrizione
    options={"build_exe": build_exe_options}, # Passiamo le opzioni di build
    executables=executables, # Passiamo la lista degli eseguibili
)