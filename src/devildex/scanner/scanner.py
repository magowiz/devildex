import re
import shutil
from pathlib import Path

from src.devildex.scanner_utils.scanner_utils import check_content_patterns, count_matching_strings, find_config_files, \
    read_file_content_robustly


def is_sphinx_project(project_path: str) -> bool:
    """
    Scansiona il percorso del progetto per determinare se è un progetto Sphinx.

    Args:
        project_path: Il percorso della directory radice del progetto da scansionare.

    Returns:
        True se il progetto è identificato come Sphinx, False altrimenti.
    """
    project_dir = Path(project_path)

    potential_conf_dirs = [
        project_dir,
        project_dir / 'docs',
        project_dir / 'doc',
        # Puoi aggiungere altre directory qui se necessario, ad esempio:
        # project_dir / 'build' / 'docs',
    ]
    
    # Usa la utility per trovare i file di configurazione di Sphinx ('conf.py')
    conf_file_paths = find_config_files(potential_conf_dirs, 'conf.py')

    if not conf_file_paths:
        print(f"  ❌ Nessun file 'conf.py' trovato in posizioni standard per {project_path}")
        return False

    print(f"  🔍 Trovati {len(conf_file_paths)} file 'conf.py'. Analizzo il contenuto...")

    for conf_file_path in conf_file_paths:
        print(f"    Analizzando: {conf_file_path}")
        
        # Usa la utility per leggere il contenuto del file in modo robusto
        content = read_file_content_robustly(conf_file_path)
        if content is None:
            continue # Passa al prossimo file o termina se non ci sono altri file da controllare

        # --- CRITERI DI FORZA MASSIMA E ELEVATA (molto difficili da falsificare) ---
        # Definisci i pattern regex e i messaggi di successo per i controlli ad alta priorità specifici di Sphinx
        high_priority_sphinx_checks = [
            (r"extensions\s*=\s*\[.*?['\"]sphinx\.ext\.(autodoc|napoleon|intersphinx|viewcode|todo|coverage)['\"].*?\]",
             "Trovata estensione 'sphinx.ext.*' chiave in 'extensions'. Molto probabilmente Sphinx."),
            (r"html_theme\s*=\s*['\"](alabaster|sphinx_rtd_theme|furo|pydata_sphinx_theme)['\"]",
             "Trovato 'html_theme' con tema Sphinx conosciuto. Molto probabilmente Sphinx."),
            (r"https://www\.sphinx-doc\.org/en/master/usage/configuration\.html",
             "Trovato link alla documentazione ufficiale Sphinx. Probabilmente Sphinx."),
            # Regex per il setup del sys.path, che può essere su una o più righe
            (r"import os\s*;\s*import sys\s*;\s*sys\.path\.insert\(0,\s*os\.path\.abspath\(",
             "Trovato setup comune del sys.path per autodoc. Forte indicazione.")
        ]
        
        # Usa la utility per controllare i pattern e ottenere il messaggio di successo
        success_message = check_content_patterns(content, high_priority_sphinx_checks, re.DOTALL | re.MULTILINE)
        if success_message:
            print(f"    ✅ {success_message}")
            return True

        # --- CRITERI DI FORZA MEDIA (richiedono combinazione) ---
        # Definisci le stringhe delle variabili comuni di configurazione di Sphinx
        common_sphinx_vars = [
            "project =", "copyright =", "author =", "source_suffix =", "master_doc =",
            "version =", "release =", "templates_path =", "exclude_patterns ="
        ]

        # Usa la utility per contare quante di queste variabili sono presenti
        score = count_matching_strings(content, common_sphinx_vars)
        
        if score >= 3: # La soglia di 3 variabili trovate
            print(f"    ✅ Trovate {score} variabili di configurazione Sphinx comuni. Buona indicazione.")
            return True

    print(f"  ❌ Nessun criterio Sphinx forte trovato nel file 'conf.py' per {project_path}.")
    return False

# --- ESEMPIO DI UTILIZZO E TEST ---
if __name__ == "__main__":
    print("--- Test su una directory ESEMPIO_SPHINX ---")
    
    # Setup per il primo test: conf.py nella root
    test_sphinx_dir = Path("./ESEMPIO_SPHINX_DOCS")
    test_sphinx_dir.mkdir(exist_ok=True)
    (test_sphinx_dir / "conf.py").write_text("""
# conf.py
# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys
sys.path.insert(0, os.path.abspath('.'))
project = 'My Test Project'
copyright = '2024, Me'
author = 'Me'
version = '0.1'
release = '0.1.0'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]
html_theme = 'sphinx_rtd_theme'
source_suffix = '.rst'
master_doc = 'index'
""")

    # Setup per il secondo test: conf.py in 'docs/'
    test_sphinx_dir_docs = Path("./ESEMPIO_SPHINX_PROJ")
    test_sphinx_dir_docs.mkdir(exist_ok=True)
    (test_sphinx_dir_docs / "docs").mkdir(exist_ok=True)
    (test_sphinx_dir_docs / "docs" / "conf.py").write_text("""
# conf.py per un progetto con docs/
project = 'Another Test Project'
copyright = '2024, Tester'
author = 'Tester'
extensions = [
    'sphinx.ext.todo',
    'sphinx.ext.intersphinx',
]
html_theme = 'alabaster'
""")
    (test_sphinx_dir_docs / "src").mkdir(exist_ok=True) # Simula la presenza di codice sorgente

    print(f"\nScansione di {test_sphinx_dir.name}/:")
    if is_sphinx_project(str(test_sphinx_dir)):
        print(f"Risultato finale: {test_sphinx_dir.name} è un progetto Sphinx.")
    else:
        print(f"Risultato finale: {test_sphinx_dir.name} NON è un progetto Sphinx.")

    print(f"\nScansione di {test_sphinx_dir_docs.name}/:")
    if is_sphinx_project(str(test_sphinx_dir_docs)):
        print(f"Risultato finale: {test_sphinx_dir_docs.name} è un progetto Sphinx.")
    else:
        print(f"Risultato finale: {test_sphinx_dir_docs.name} NON è un progetto Sphinx.")

    print("\n--- Test su una directory che NON è Sphinx (simulazione) ---")
    
    # Test con un conf.py che non è Sphinx
    test_non_sphinx_dir = Path("./ESEMPIO_NON_SPHINX")
    test_non_sphinx_dir.mkdir(exist_ok=True)
    (test_non_sphinx_dir / "conf.py").write_text("""
# Questa è una configurazione per un'altra cosa
MY_APP_NAME = "My Custom App"
DEBUG_MODE = True
LOG_LEVEL = "INFO"
""")
    
    # Test con una directory senza conf.py
    test_non_sphinx_dir_no_conf = Path("./ESEMPIO_SENZA_CONF")
    test_non_sphinx_dir_no_conf.mkdir(exist_ok=True)

    print(f"\nScansione di {test_non_sphinx_dir.name}/:")
    if is_sphinx_project(str(test_non_sphinx_dir)):
        print(f"Risultato finale: {test_non_sphinx_dir.name} è un progetto Sphinx.")
    else:
        print(f"Risultato finale: {test_non_sphinx_dir.name} NON è un progetto Sphinx.")

    print(f"\nScansione di {test_non_sphinx_dir_no_conf.name}/:")
    if is_sphinx_project(str(test_non_sphinx_dir_no_conf)):
        print(f"Risultato finale: {test_non_sphinx_dir_no_conf.name} è un progetto Sphinx.")
    else:
        print(f"Risultato finale: {test_non_sphinx_dir_no_conf.name} NON è un progetto Sphinx.")

    # Pulizia delle directory di test
    print("\nPulizia directory di test...")
    shutil.rmtree(test_sphinx_dir, ignore_errors=True)
    shutil.rmtree(test_sphinx_dir_docs, ignore_errors=True)
    shutil.rmtree(test_non_sphinx_dir, ignore_errors=True)
    shutil.rmtree(test_non_sphinx_dir_no_conf, ignore_errors=True)
    print("Fatto.")