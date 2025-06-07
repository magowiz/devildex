"""sample data module."""

from devildex.models import PackageDetails

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
        "version": "1.2.1",
        "description": "Core library of the system",
        "status": "Installed",
        "versions": [
            {"ver_id": "pkg1_v3", "version_str": "1.2.1", "date": "2023-05-10"},
        ],
    },
]

COLUMNS_ORDER = ["id", "name", "version", "description", "status", "docset_status"]


for item in PACKAGES_DATA:
    item["docset_status"] = "Not Available"
    if "version" not in item:
        item["version"] = "N/A"
        versions_list = item.get("versions")
        if isinstance(versions_list, list) and versions_list:
            last_version_detail = versions_list[-1]
            if isinstance(last_version_detail, dict):
                item["version"] = last_version_detail.get("version_str", "N/A")

PACKAGES_DATA_AS_DETAILS: list[PackageDetails] = []
for pkg_dict in PACKAGES_DATA:
    try:
        details = PackageDetails.from_dict(pkg_dict)
        PACKAGES_DATA_AS_DETAILS.append(details)
    except Exception as e:
        print(
            f"Errore nella conversione del dizionario di esempio in PackageDetails: {pkg_dict}, errore: {e}"
        )
