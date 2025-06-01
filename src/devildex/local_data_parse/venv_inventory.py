"""venv inventory module."""

import importlib.metadata

from devildex.models import PackageDetails

PART_LENGTH = 2

def get_installed_packages_with_project_urls(explicit: set | None = None) -> list:
    """Restituisce una lista di oggetti PackageDetails per tutti i pacchetti installati.

    (o per quelli specificati esplicitamente), includendo nome, versione
    e un dizionario dei loro Project-URL.
    """
    package_list: list[PackageDetails] = []
    for dist in importlib.metadata.distributions():
        if explicit and dist.name not in explicit:
            continue

        package_name = dist.name
        package_version = dist.version
        metadata = dist.metadata
        current_project_urls = {}

        project_url_entries = metadata.get_all("Project-URL")

        if project_url_entries:
            for url_entry in project_url_entries:
                try:
                    parts = [part.strip() for part in url_entry.split(",", 1)]
                    if len(parts) == PART_LENGTH:
                        label, url_value = parts
                        current_project_urls[label] = url_value
                    else:
                        print(
                            f"Attenzione: Impossibile analizzare la voce Project-URL per {package_name}: '{url_entry}'"
                        )
                except Exception as e:
                    print(
                        f"Errore nell'analizzare la voce Project-URL '{url_entry}' per {package_name}: {e}"
                    )
        pkg_details = PackageDetails(
            name=package_name,
            version=package_version,
            project_urls=current_project_urls,
        )
        package_list.append(pkg_details)

    return package_list
