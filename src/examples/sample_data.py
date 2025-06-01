"""sample data module."""
PACKAGES_DATA = [
    {
        "id": "pkg1",
        "name": "Alpha Package",
        "description": "Core library of the system",  # Tradotto
        "status": "Installed",
        "versions": [
            {"ver_id": "pkg1_v1", "version_str": "1.0.5", "date": "2023-01-15"},
            {"ver_id": "pkg1_v2", "version_str": "1.1.0", "date": "2023-03-20"},
            {"ver_id": "pkg1_v3", "version_str": "1.2.1", "date": "2023-05-10"},
        ],
    },
    {
        "id": "pkg2",
        "name": "Beta Module",
        "description": "File management utility",  # Tradotto
        "status": "Not Installed",
        "versions": [{"ver_id": "pkg2_v1", "version_str": "2.3.0", "date": "2023-06-01"}],
    },
    {
        "id": "pkg3",
        "name": "Gamma Component",
        "description": "Advanced user interface",
        "status": "Update Available",
        "versions": [],
    },
    {
        "id": "pkg4",
        "name": "Delta Service",
        "description": "API for external services",
        "status": "Installed",
        "versions": [
            {"ver_id": "pkg4_v1", "version_str": "0.9.1", "date": "2022-11-05"},
            {"ver_id": "pkg4_v2", "version_str": "0.9.2", "date": "2023-02-12"},
        ],
    },
]

COLUMNS_ORDER = ['id', 'name', 'description', 'status', 'docset_status']
for item in PACKAGES_DATA:
    item['docset_status'] = "Not Available"