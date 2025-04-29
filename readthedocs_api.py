import os
from urllib.parse import urlparse

import requests


def _get_project_slug(rtd_url):
    """Estrae lo slug del progetto Read the Docs da un URL."""
    print(f"Analizzo l'URL: {rtd_url}")
    parsed_url = urlparse(rtd_url)
    path_parts = [part for part in parsed_url.path.split("/") if part]
    project_slug = parsed_url.hostname.split(".")[0]

    if project_slug == "readthedocs" and path_parts:
        project_slug = path_parts[0]
    elif not project_slug or project_slug == "www" or project_slug == "readthedocs":
        if path_parts:
            project_slug = path_parts[0]
        else:
            print("Errore: Impossibile dedurre lo slug del progetto dall'URL.")
            return None

    print(f"Slug del progetto dedotto: {project_slug}")
    return project_slug


def _fetch_available_versions(project_slug):
    """Recupera le versioni disponibili per un progetto dall'API RTD."""
    api_list_versions_url = (
        f"https://readthedocs.org/api/v3/projects/{project_slug}/versions/"
    )
    print(f"\nChiamo l'API per listare le versioni: {api_list_versions_url}")
    try:
        response = requests.get(api_list_versions_url)
        response.raise_for_status()
        versions_list_data = response.json()
        print(
            "API lista versioni chiamata con successo. Trovate "
            f"{versions_list_data.get('count', 'N/A')} versioni."
        )
        return versions_list_data.get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"Errore chiamando API lista versioni ({api_list_versions_url}): {e}")
        return None
    except Exception as e:
        print(f"Si è verificato un errore inatteso listando le versioni: {e}")
        return None


def _choose_best_version(available_versions, preferred_versions):
    """Sceglie lo slug della versione migliore tra quelle disponibili."""
    if not available_versions:
        print(
            "Errore: Nessuna versione disponibile fornita per la scelta."
        )
        return None

    print("Versioni disponibili (slug, attivo, costruito):")
    for version in available_versions:
        print(
            f"- {version.get('slug')}: Active={version.get('active')}, Built={version.get('built')}"
        )

    for preferred in preferred_versions:
        for version in available_versions:
            if (
                version.get("slug") == preferred
                and version.get("active")
                and version.get("built")
            ):
                print(
                    f"\nScelta versione preferita e disponibile: '{preferred}'"
                )
                return preferred

    print(
        "\nNessuna versione preferita disponibile (attiva e costruita). Provo a prendere "
        "la prima versione attiva e costruita trovata."
    )
    for version in available_versions:
        if version.get("active") and version.get("built"):
            chosen_slug = version.get("slug")
            print(
                f"Scelta prima versione attiva e costruita: '{chosen_slug}'"
            )
            return chosen_slug

    print(
        "\nErrore: Nessuna versione attiva e costruita trovata tra quelle disponibili."
    )
    return None


def _fetch_version_details(project_slug, version_slug):
    """Recupera i dettagli di una specifica versione dall'API RTD."""
    api_version_detail_url = (
        f"https://readthedocs.org/api/v3/versions/{version_slug}/"
    )
    print(
        f"\nChiamo l'API per i dettagli della versione '{version_slug}': "
        f"{api_version_detail_url} con project__slug={project_slug}"
    )
    try:
        response = requests.get(
            api_version_detail_url, params={"project__slug": project_slug}
        )
        response.raise_for_status()
        version_detail_data = response.json()
        print(
            f"API dettagli versione chiamata con successo per '{version_slug}'."
        )
        return version_detail_data
    except requests.exceptions.RequestException as e:
        print(
            f"Errore chiamando API dettagli versione ({api_version_detail_url}?"
            f"project__slug={project_slug}): {e}"
        )
        return None
    except Exception as e:
        print(
            f"Si è verificato un errore inatteso ottenendo i dettagli della versione: {e}"
        )
        return None


def _get_download_url(version_details, download_format):
    """Estrae l'URL di download per il formato specificato dai dettagli della versione."""
    if not version_details:
        print("Errore: Dettagli versione non disponibili per trovare l'URL di download.")
        return None

    download_urls = version_details.get("downloads")
    if not download_urls:
        version_slug = version_details.get('slug', 'sconosciuta')
        print(
            f"Errore: Campo 'downloads' non trovato nei dettagli per la versione "
            f"'{version_slug}'."
        )
        print("Assicurati che i formati offline siano abilitati per questa versione.")
        return None

    file_url = download_urls.get(download_format)
    if not file_url:
        version_slug = version_details.get('slug', 'sconosciuta')
        print(
            f"Errore: Formato '{download_format}' non disponibile per la versione "
            f"'{version_slug}'."
        )
        print(f"Formati disponibili: {list(download_urls.keys())}")
        return None

    if file_url.startswith("//"):
        file_url = "https:" + file_url

    if not file_url.lower().endswith((".zip", ".pdf", ".epub")):
        print(
            f"Avviso: L'URL trovato '{file_url}' potrebbe non essere un link "
            "diretto al file scaricabile (estensione non riconosciuta). Procedo comunque..."
        )

    print(
        f"\nTrovato URL per {download_format} versione "
        f"'{version_details.get('slug', 'sconosciuta')}': {file_url}"
    )
    return file_url


def _determine_local_filename(project_slug, version_slug, download_url, download_format):
    """Determina un nome file locale sensato per il download."""
    file_extension = download_format.replace("htmlzip", "zip")
    filename_from_url = download_url.split("/")[-1]

    if "." in filename_from_url and len(filename_from_url) <= 60:
        local_filename = filename_from_url
    else:
        local_filename = f"{project_slug}-{version_slug}.{file_extension}"

    return local_filename


def _download_file(file_url, local_filepath):
    """Scarica un file da un URL in un percorso locale."""
    print(f"Scarico il file in: {local_filepath}")
    try:
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            with open(local_filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Download completato: {local_filepath}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il download del file ({file_url}): {e}")
        if os.path.exists(local_filepath):
            try:
                os.remove(local_filepath)
                print(f"File parziale rimosso: {local_filepath}")
            except OSError as remove_err:
                print(f"Errore durante la rimozione del file parziale: {remove_err}")
        return False
    except Exception as e:
        print(f"Si è verificato un errore inatteso durante il download del file: {e}")
        return False


def download_readthedocs_prebuilt_robust(
    rtd_url, preferred_versions=["stable", "latest"], download_format="htmlzip"
):
    """
    Scarica una versione pre-confezionata della documentazione da Read the Docs
    utilizzando funzioni helper per maggiore chiarezza e manutenibilità.

    Args:
        rtd_url (str): L'URL base del progetto Read the Docs (es. https://black.readthedocs.io/).
        preferred_versions (list): Elenco di slug di versioni da privilegiare (in ordine).
        download_format (str): Il formato da scaricare (es. 'htmlzip', 'pdf', 'epub').

    Returns:
        str: Il percorso del file scaricato, o None in caso di fallimento.
    """
    print("--- Processo Download Robusto (Rifattorizzato) ---")

    project_slug = _get_project_slug(rtd_url)
    if not project_slug:
        return None

    available_versions = _fetch_available_versions(project_slug)
    if available_versions is None:
        return None

    chosen_version_slug = _choose_best_version(available_versions, preferred_versions)
    if not chosen_version_slug:
        return None

    version_details = _fetch_version_details(project_slug, chosen_version_slug)
    if not version_details:
        return None

    file_url = _get_download_url(version_details, download_format)
    if not file_url:
        return None

    local_filename = _determine_local_filename(
        project_slug, chosen_version_slug, file_url, download_format
    )
    output_dir = "rtd_prebuilt_downloads_robust"
    os.makedirs(output_dir, exist_ok=True)
    local_filepath = os.path.join(output_dir, local_filename)

    if _download_file(file_url, local_filepath):
        return local_filepath
    else:
        return None


print("--- Esecuzione Script 1 (Versione 3: Robusta - Rifattorizzata) ---")

print("Provando con: https://black.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://black.readthedocs.io/")
if downloaded_file:
    print(f"Download successo per Black: {downloaded_file}")
else:
    print("Download fallito per Black.")
print("-" * 30)

print("Provando con: https://requests.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust(
    "https://requests.readthedocs.io/"
)
if downloaded_file:
    print(f"Download successo per Requests: {downloaded_file}")
else:
    print("Download fallito per Requests.")
print("-" * 30)

print("Provando con: https://sphinx.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://sphinx.readthedocs.io/")
if downloaded_file:
    print(f"Download successo per Sphinx: {downloaded_file}")
else:
    print("Download fallito per Sphinx.")
print("-" * 30)

print("--- Esecuzione Script 1 (Versione 3: Robusta) ---")

print("Provando con: https://black.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://black.readthedocs.io/")
if downloaded_file:
    print(f"Download successo per Black: {downloaded_file}")
else:
    print("Download fallito per Black.")
print("-" * 30)

print("Provando con: https://requests.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust(
    "https://requests.readthedocs.io/"
)
if downloaded_file:
    print(f"Download successo per Requests: {downloaded_file}")
else:
    print("Download fallito per Requests.")
print("-" * 30)

print("Provando con: https://sphinx.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://sphinx.readthedocs.io/")
if downloaded_file:
    print(f"Download successo per Sphinx: {downloaded_file}")
else:
    print("Download fallito per Sphinx.")
print("-" * 30)
