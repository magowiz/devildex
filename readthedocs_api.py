import os
from urllib.parse import urlparse

import requests


def download_readthedocs_prebuilt_robust(
    rtd_url, preferred_versions=["stable", "latest"], download_format="htmlzip"
):
    """
    Scarica una versione pre-confezionata della documentazione da Read the Docs
    seguendo un processo API più robusto: lista le versioni, sceglie la migliore,
    poi ottiene i dettagli e scarica l'artefatto.

    Args:
        rtd_url (str): L'URL base del progetto Read the Docs (es. https://black.readthedocs.io/).
        preferred_versions (list): Elenco di slug di versioni da privilegiare (in ordine).
        download_format (str): Il formato da scaricare (es. 'htmlzip', 'pdf', 'epub').

    Returns:
        str: Il percorso del file scaricato, o None in caso di fallimento.
    """
    print("--- Processo Download Robusto ---")
    print(f"Analizzo l'URL: {rtd_url}")

    # --- Passo 1: Deducire lo slug del progetto ---
    parsed_url = urlparse(rtd_url)
    path_parts = [part for part in parsed_url.path.split("/") if part]
    project_slug = parsed_url.hostname.split(".")[0]
    if project_slug == "readthedocs" and path_parts:
        project_slug = path_parts[0]
    elif not project_slug or project_slug == "readthedocs":
        if path_parts:
            project_slug = path_parts[0]
        else:
            print("Errore: Impossibile dedurre lo slug del progetto dall'URL.")
            return None

    print(f"Slug del progetto dedotto: {project_slug}")

    # --- Passo 2: Listare le versioni disponibili tramite API ---
    # Endpoint: GET /api/v3/projects/{project_slug}/versions/
    api_list_versions_url = (
        f"https://readthedocs.org/api/v3/projects/{project_slug}/versions/"
    )

    print(f"\nChiamo l'API per listare le versioni: {api_list_versions_url}")

    versions_list_data = None
    try:
        response = requests.get(api_list_versions_url)
        response.raise_for_status()  # Genera eccezione per errori HTTP (come 404)

        versions_list_data = response.json()
        print(
            "API lista versioni chiamata con successo. Trovate "
            f"{versions_list_data.get('count', 'N/A')} versioni."
        )

    except requests.exceptions.RequestException as e:
        print(f"Errore chiamando API lista versioni ({api_list_versions_url}): {e}")
        print(
            "Impossibile ottenere l'elenco delle versioni. Non posso procedere "
            "a scegliere la versione."
        )
        return None
    except Exception as e:
        print(f"Si è verificato un errore inatteso listando le versioni: {e}")
        return None

    # --- Passo 3: Scegliere la migliore versione dalla lista ---
    chosen_version_slug = None
    available_versions = versions_list_data.get("results", [])

    if not available_versions:
        print(
            "Errore: L'API non ha restituito nessuna versione disponibile per questo progetto."
        )
        return None

    print("Versioni disponibili (slug, attivo, costruito):")
    for version in available_versions:
        print(
            f"- {version.get('slug')}: Active={version.get('active')}, Built={version.get('built')}"
        )

    # Cerca tra le versioni preferite se sono attive e costruite
    for preferred in preferred_versions:
        for version in available_versions:
            if (
                version.get("slug") == preferred
                and version.get("active")
                and version.get("built")
            ):
                chosen_version_slug = preferred
                print(
                    f"\nScelta versione preferita e disponibile: '{chosen_version_slug}'"
                )
                break  # Esci dal ciclo interno
        if chosen_version_slug:
            break  # Esci dal ciclo esterno

    # Se nessuna versione preferita trovata, prova a prendere la prima attiva e costruita
    if not chosen_version_slug:
        print(
            "\nNessuna versione preferita disponibile (attiva e costruita). Provo a prendere "
            "la prima versione attiva e costruita trovata."
        )
        for version in available_versions:
            if version.get("active") and version.get("built"):
                chosen_version_slug = version.get("slug")
                print(
                    f"Scelta prima versione attiva e costruita: '{chosen_version_slug}'"
                )
                break

    if not chosen_version_slug:
        print(
            "\nErrore: Nessuna versione attiva e costruita trovata tra quelle disponibili."
        )
        return None

    # --- Passo 4: Ottenere i dettagli della versione scelta tramite API ---
    # Endpoint: GET /api/v3/versions/{version_slug}/?project__slug={project_slug}
    api_version_detail_url = (
        f"https://readthedocs.org/api/v3/versions/{chosen_version_slug}/"
    )

    print(
        f"\nChiamo l'API per i dettagli della versione '{chosen_version_slug}': "
        f"{api_version_detail_url} con project__slug={project_slug}"
    )

    version_detail_data = None
    try:
        response = requests.get(
            api_version_detail_url, params={"project__slug": project_slug}
        )
        response.raise_for_status()

        version_detail_data = response.json()
        print(
            f"API dettagli versione chiamata con successo per '{chosen_version_slug}'."
        )

    except requests.exceptions.RequestException as e:
        print(
            f"Errore chiamando API dettagli versione ({api_version_detail_url}?"
            f"project__slug={project_slug}): {e}"
        )
        print(
            "Impossibile ottenere i dettagli della versione. Non posso ottenere i link di download."
        )
        return None
    except Exception as e:
        print(
            f"Si è verificato un errore inatteso ottenendo i dettagli della versione: {e}"
        )
        return None

    # --- Passo 5: Estrarre l'URL di download ---
    download_urls = version_detail_data.get("downloads")
    if not download_urls:
        print(
            "Errore: Campo 'downloads' non trovato nei dettagli per la versione "
            f"'{chosen_version_slug}'."
        )
        print("Assicurati che i formati offline siano abilitati per questa versione.")
        return None

    file_url = download_urls.get(download_format)
    if not file_url:
        print(
            f"Errore: Formato '{download_format}' non disponibile per la versione "
            f"'{chosen_version_slug}'."
        )
        print(f"Formati disponibili: {list(download_urls.keys())}")
        return None

    # Rendi l'URL assoluto se necessario
    if file_url.startswith("//"):
        file_url = "https:" + file_url
    # Avviso se l'URL non sembra un link diretto al file (basato sull'estensione)
    if not file_url.lower().endswith((".zip", ".pdf", ".epub")):
        print(
            f"Avviso: L'URL trovato '{file_url}' potrebbe non essere un link "
            "diretto al file scaricabile (estensione non riconosciuta). Procedo comunque..."
        )

    print(
        f"\nTrovato URL per {download_format} versione '{chosen_version_slug}': {file_url}"
    )

    # --- Passo 6: Scaricare il file effettivo ---
    output_dir = "rtd_prebuilt_downloads_robust"
    os.makedirs(output_dir, exist_ok=True)

    file_extension = download_format.replace("htmlzip", "zip")
    # Tenta di ottenere un nome file più pulito dall'URL se possibile
    filename_from_url = file_url.split("/")[-1]
    if "." not in filename_from_url or len(filename_from_url) > 50:
        local_filename = f"{project_slug}-{chosen_version_slug}.{file_extension}"
    else:
        local_filename = filename_from_url

    local_filepath = os.path.join(output_dir, local_filename)

    print(f"Scarico il file in: {local_filepath}")

    try:
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()  # Genera eccezione per errori HTTP durante il download
            with open(local_filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Download completato: {local_filepath}")
        return local_filepath  # Restituisce il percorso del file scaricato

    except requests.exceptions.RequestException as e:
        print(f"Errore durante il download del file ({file_url}): {e}")
        return None
    except Exception as e:
        print(f"Si è verificato un errore inatteso durante il download del file: {e}")
        return None


# --- Esempi di utilizzo ---
print("--- Esecuzione Script 1 (Versione 3: Robusta) ---")

# Esempio 1: Prova con Black (potrebbe fallire a causa dei precedenti errori API)
print("Provando con: https://black.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://black.readthedocs.io/")
if downloaded_file:
    print(f"Download successo per Black: {downloaded_file}")
else:
    print("Download fallito per Black.")
print("-" * 30)

# Esempio 2: Prova con Requests (dovrebbe funzionare se API è online)
print("Provando con: https://requests.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust(
    "https://requests.readthedocs.io/"
)
if downloaded_file:
    print(f"Download successo per Requests: {downloaded_file}")
else:
    print("Download fallito per Requests.")
print("-" * 30)

# Esempio 3: Prova con Sphinx (dovrebbe funzionare)
print("Provando con: https://sphinx.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://sphinx.readthedocs.io/")
if downloaded_file:
    print(f"Download successo per Sphinx: {downloaded_file}")
else:
    print("Download fallito per Sphinx.")
print("-" * 30)
