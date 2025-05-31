PACKAGES_DATA = [
    {
        "id": "pkg1",
        "name": "Pacchetto Alpha",
        "description": "Libreria Core del sistema",
        "status": "Installato",
        "versions": [
            {"ver_id": "pkg1_v1", "version_str": "1.0.5", "date": "2023-01-15"},
            {"ver_id": "pkg1_v2", "version_str": "1.1.0", "date": "2023-03-20"},
            {"ver_id": "pkg1_v3", "version_str": "1.2.1", "date": "2023-05-10"},
        ],
    },
    {
        "id": "pkg2",
        "name": "Modulo Beta",
        "description": "Utility per la gestione file",
        "status": "Non Installato",
        "versions": [{"ver_id": "pkg2_v1", "version_str": "2.3.0", "date": "2023-06-01"}], # Singola versione, potrebbe non essere espandibile
    },
    {
        "id": "pkg3",
        "name": "Componente Gamma",
        "description": "Interfaccia utente avanzata",
        "status": "Aggiornamento Disponibile",
        "versions": [], # Nessuna versione esplicita, riga singola
    },
    {
        "id": "pkg4",
        "name": "Servizio Delta",
        "description": "API per servizi esterni",
        "status": "Installato",
        "versions": [
            {"ver_id": "pkg4_v1", "version_str": "0.9.1", "date": "2022-11-05"},
            {"ver_id": "pkg4_v2", "version_str": "0.9.2", "date": "2023-02-12"},
        ],
    },
]

COLUMNS_ORDER = ['id', 'name', 'description', 'status']