# /home/magowiz/MEGA/projects/devildex/src/examples/sample_data.py
"""sample data module."""

PACKAGES_DATA = [
    {
        "id": "real_pkg_black", # ID univoco per la GUI
        "name": "black",
        "version": "24.4.2", # Versione specifica
        "description": "The uncompromising Python code formatter", # Descrizione (puoi aggiungerla)
        "status": "Not Installed", # O "Installed" se vuoi simulare che sia già presente
        "project_urls": { # Dati da PACKAGES_TO_TEST
            "Source Code": "https://github.com/psf/black.git",
            "Documentation": "https://black.readthedocs.io/",
        },
        # Potresti voler mantenere la struttura "versions" se la tua GUI la usa
        # per mostrare uno storico o permettere la selezione,
        # altrimenti la chiave "version" a livello principale è sufficiente
        # per l'integrazione con l'Orchestrator.
        # "versions": [
        #     {"ver_id": "black_24.4.2", "version_str": "24.4.2", "date": "2024-04-01"},
        # ],
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
        # "versions": [
        #     {"ver_id": "flask_3.0.3", "version_str": "3.0.3", "date": "2024-03-01"},
        # ],
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
    # Puoi aggiungere altri pacchetti reali da PACKAGES_TO_TEST qui...
    # Esempio di un pacchetto fittizio mantenuto per testare fallimenti:
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
    if "version" not in item and item.get("versions"): # Se 'version' manca ma 'versions' esiste
        # Prendi l'ultima versione dalla lista come default
        # Questo è un esempio, potresti avere una logica diversa
        if item["versions"]:
            item["version"] = item["versions"][-1]["version_str"]
        else:
            item["version"] = "N/A" # O un altro placeholder se non ci sono versioni
    elif "version" not in item:
        item["version"] = "N/A" # Placeholder se mancano sia 'version' che 'versions'
