"""Provides default sample data for DevilDex.

This module includes:
- PACKAGES_DATA: A list of raw package data dictionaries.
- COLUMNS_ORDER: A predefined order for displaying package attributes.
- PACKAGES_DATA_AS_DETAILS: A list of PackageDetails objects,
  processed from PACKAGES_DATA.
"""

from typing import Any

from devildex.models import PackageDetails
NOT_INSTALLED_STATUS = "Not Installed"
PACKAGES_DATA: list[dict[str, Any]] = [
    {
        "id": "real_pkg_black",
        "name": "black",
        "version": "24.4.2",
        "description": "The uncompromising Python code formatter",
        "status": NOT_INSTALLED_STATUS,
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
        "status": NOT_INSTALLED_STATUS,
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
        "status": NOT_INSTALLED_STATUS,
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

COLUMNS_ORDER: list[str] = [
    "id",
    "name",
    "version",
    "description",
    "status",
    "docset_status",
]

for item in PACKAGES_DATA:
    item["docset_status"] = "Not Available"  # Default docset status

    # Determine the version string to use with clear priority:
    # 1. From 'versions' list (last entry's 'version_str')
    # 2. From top-level 'version' key
    # 3. Default to "N/A"
    final_version_str = "N/A"  # Default

    versions_list = item.get("versions")
    if isinstance(versions_list, list) and versions_list:
        last_version_detail = versions_list[-1]
        if (
            isinstance(last_version_detail, dict)
            and "version_str" in last_version_detail
        ):
            final_version_str = last_version_detail["version_str"]

    if final_version_str == "N/A" and "version" in item:
        final_version_str = item["version"]

    item["version"] = final_version_str


PACKAGES_DATA_AS_DETAILS: list[PackageDetails] = []
for pkg_dict in PACKAGES_DATA:
    details = PackageDetails.from_dict(pkg_dict)
    PACKAGES_DATA_AS_DETAILS.append(details)
