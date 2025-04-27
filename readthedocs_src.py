import requests
import os
import subprocess
import shutil
from urllib.parse import urlparse

def find_and_copy_doc_source(repo_path, output_base_dir, project_slug):
    """
    Cerca le directory sorgente della documentazione all'interno di una repository clonata
    e copia la prima trovata in una cartella di output dedicata.

    Args:
        repo_path (str): Il percorso locale alla repository clonata.
        output_base_dir (str): La directory base dove salvare i sorgenti isolati.
        project_slug (str): Lo slug del progetto, usato per nominare la cartella di output.

    Returns:
        str: Il percorso alla directory dei sorgenti di documentazione isolati, o None se non trovati/copiati.
    """
    print(f"\nRicerca directory sorgente documentazione in: {repo_path}")

    potential_doc_dirs = ['docs', 'doc', 'Doc']

    found_doc_path = None
    for doc_dir_name in potential_doc_dirs:
        current_path = os.path.join(repo_path, doc_dir_name)
        if os.path.isdir(current_path):
            found_doc_path = current_path
            print(f"Trovata directory sorgente documentazione potenziale: {found_doc_path}")
            break

    if not found_doc_path:
        print("Nessuna directory sorgente documentazione comune trovata.")
        return None

    isolated_doc_dir_name = f"{project_slug}_doc_source"
    isolated_doc_path = os.path.join(output_base_dir, isolated_doc_dir_name)

    if os.path.exists(isolated_doc_path):
        print(f"La directory di destinazione per i sorgenti isolati '{isolated_doc_path}' esiste già. Salto la copia.")
        # Potresti voler gestire l'aggiornamento qui invece di saltare
        return isolated_doc_path

    print(f"Copio i sorgenti della documentazione da '{found_doc_path}' a '{isolated_doc_path}'")
    try:
        shutil.copytree(found_doc_path, isolated_doc_path)
        print("Copia dei sorgenti completata.")
        return isolated_doc_path
    except Exception as e:
        print(f"Errore durante la copia dei sorgenti della documentazione: {e}")
        return None


def download_readthedocs_source_and_clean(rtd_url):
    """
    Cerca di ottenere l'URL del repository sorgente di un progetto Read the Docs,
    clona/trova il repository, cerca/copia i sorgenti della documentazione,
    e infine elimina la repository clonata.

    Args:
        rtd_url (str): L'URL base del progetto Read the Docs (es. https://black.readthedocs.io/).

    Returns:
        str: Il percorso alla directory dei sorgenti di documentazione isolati, o None in caso di fallimento.
    """
    print(f"--- Processo Download Sorgente e Pulizia ---")
    print(f"Analizzo l'URL: {rtd_url}")

    parsed_url = urlparse(rtd_url)
    path_parts = [part for part in parsed_url.path.split('/') if part]
    project_slug = parsed_url.hostname.split('.')[0]
    if project_slug == 'readthedocs' and path_parts:
        project_slug = path_parts[0]
    elif not project_slug or project_slug == 'readthedocs':
         if path_parts:
             project_slug = path_parts[0]
         else:
              print("Errore: Impossibile dedurre lo slug del progetto dall'URL.")
              return None

    print(f"Slug del progetto dedotto: {project_slug}")

    api_project_detail_url = f"https://readthedocs.org/api/v3/projects/{project_slug}/"

    print(f"Chiamo l'API per i dettagli del progetto: {api_project_detail_url}")

    repo_url = None
    default_branch = 'main'

    try:
        response = requests.get(api_project_detail_url)
        response.raise_for_status()

        project_data = response.json()

        repo_data = project_data.get('repository')
        if repo_data:
             repo_url = repo_data.get('url')
             default_branch = project_data.get('default_branch', 'main')

        if not repo_url:
            print(f"Avviso: URL del repository sorgente non trovato per il progetto '{project_slug}' tramite API.")
            print("Non posso clonare la repository.")
        else:
             print(f"Trovato URL repository: {repo_url}")
             print(f"Branch di default: {default_branch}")

    except requests.exceptions.RequestException as e:
        print(f"Avviso: Errore durante la richiesta API per i dettagli del progetto: {e}")
        print("Provo a cercare la repository clonata localmente se esiste già.")
        # Non ritornare, continua per cercare la directory clonata localmente

    # --- Parte Gestione Clone o Ricerca Locale ---
    base_output_dir = "rtd_source_clones_temp" # Directory temporanea per i cloni
    os.makedirs(base_output_dir, exist_ok=True)

    clone_dir_name = f"{project_slug}_repo_{default_branch}" # Nome della cartella clone
    clone_dir_path = os.path.join(base_output_dir, clone_dir_name) # Percorso completo clone

    cloned_repo_exists_before = os.path.exists(clone_dir_path) # Controlla se esisteva prima di clonare

    if repo_url and not cloned_repo_exists_before:
        print(f"Clono il repository (branch '{default_branch}') in: {clone_dir_path}")
        try:
            subprocess.run(
                ['git', 'clone', '--depth', '1', '--branch', default_branch, repo_url, clone_dir_path],
                check=True,
                capture_output=True,
                text=True
            )
            print("Comando git clone eseguito con successo.")
        except subprocess.CalledProcessError as e:
            print(f"Errore durante l'esecuzione del comando git clone:")
            print(f"Comando: {' '.join(e.cmd)}")
            print(f"Codice di uscita: {e.returncode}")
            print(f"Errore:\n{e.stderr}")
            print("Impossibile clonare. Non posso procedere.")
            # Tentare comunque la ricerca se la directory è stata creata parzialmente? No, meglio fallire qui.
            return None
        except FileNotFoundError:
             print("Errore: Il comando 'git' non è stato trovato.")
             print("Assicurati che Git sia installato.")
             return None
    elif not cloned_repo_exists_before:
        print(f"Impossibile clonare la repository (URL non disponibile) e la directory attesa '{clone_dir_path}' non esiste localmente.")
        return None
    else:
         print(f"Directory di clonazione attesa '{clone_dir_path}' trovata localmente. Procedo con la ricerca dei sorgenti al suo interno.")


    # --- Parte Ricerca e Copia Sorgenti Documentazione ---
    # Directory dove verranno salvati i sorgenti isolati (potrebbe essere diversa dalla temp dei cloni)
    isolated_docs_output_dir = "rtd_isolated_doc_sources"
    os.makedirs(isolated_docs_output_dir, exist_ok=True)

    isolated_source_path = find_and_copy_doc_source(clone_dir_path, isolated_docs_output_dir, project_slug)

    # --- Parte Pulizia (Elimina la repository clonata) ---
    if os.path.exists(clone_dir_path):
        print(f"\nElimino la directory della repository clonata: {clone_dir_path}")
        try:
            shutil.rmtree(clone_dir_path)
            print("Eliminazione completata.")
        except Exception as e:
            print(f"Errore durante l'eliminazione della repository clonata '{clone_dir_path}': {e}")
            print("Potrebbe essere necessario eliminarla manualmente.")

    # --- Risultato Finale ---
    if isolated_source_path:
         print(f"\nSorgenti documentazione isolati in: {isolated_source_path}")
         print("Questi file possono ora essere aggregati alla tua documentazione globale.")
         return isolated_source_path # Restituisce il percorso dove sono i sorgenti isolati
    else:
         print("\nImpossibile isolare i sorgenti documentazione.")
         return None


# --- Esempi di utilizzo ---
print("--- Esecuzione Script 2 (Versione 2: Sorgente + Pulizia) ---")
# Assicurati di avere Git installato sul tuo sistema per questo script
isolated_docs_folder = download_readthedocs_source_and_clean('https://black.readthedocs.io/')
if isolated_docs_folder:
    print(f"\nProcesso completato. I sorgenti della documentazione sono in: {isolated_docs_folder}")
else:
    print("\nProcesso fallito per l'isolamento dei sorgenti documentazione.")
print("-" * 30)