"""sample data module."""

PACKAGES_DATA = [
    {
        "id": "real_pkg_black",
        "name": "black",
        "version": "24.4.2",
        "description": "The uncompromising Python code formatter",
        "status": "Not Installed",
        "project_urls": {
            "Source Code": "https://github.com/psf/black.git",
            "Documentation": "https://black.readthedocs.io/",
        },
    },
    {
        "id": "real_pkg_flask",
        "name": "flask",
        "version": "3.0.3",
        "description": "A microframework for Python web applications",
        "status": "Not Installed",
        "project_urls": {
            "Source Code": "https://github.com/pallets/flask.git",
            "Documentation": "https://flask.palletsprojects.com/",
        },
    },
    {
        "id": "real_pkg_requests",
        "name": "requests",
        "version": "2.31.0",
        "description": "Python HTTP for Humans.",
        "status": "Not Installed",
        "project_urls": {
            "Source Code": "https://github.com/requests/requests.git",
            "Documentation": "https://requests.readthedocs.io/",
        },
    },
    {
        "id": "fictional_pkg1",
        "name": "Alpha Package (Fictional)",
        "version": "1.2.1", # Aggiunta per coerenza
        "description": "Core library of the system",
        "status": "Installed",
        "versions": [ # Mantenuto se la GUI lo usa
            {"ver_id": "pkg1_v3", "version_str": "1.2.1", "date": "2023-05-10"},
        ],
    },
]

# Assicurati che COLUMNS_ORDER rifletta le chiavi che vuoi visualizzare
# e che la GUI sappia come gestire la chiave "version" se la usi
# direttamente a livello del pacchetto.
COLUMNS_ORDER = ["id", "name", "version", "description", "status", "docset_status"]

# Inizializza 'docset_status' e 'version' (se non presente e c'è 'versions')
for item in PACKAGES_DATA:
    item["docset_status"] = "Not Available" # Default
    if "version" not in item and item.get("versions"):
        # Prendi l'ultima versione dalla lista come default
        # Questo è un esempio, potresti avere una logica diversa
        if item["versions"]:
            item["version"] = item["versions"][-1]["version_str"]
        else:
            item["version"] = "N/A" # O un altro placeholder se non ci sono versioni
    elif "version" not in item:
        item["version"] = "N/A" # Placeholder se mancano sia 'version' che 'versions'
