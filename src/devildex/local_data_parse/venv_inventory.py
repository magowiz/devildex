"""venv inventory module."""

import importlib.metadata
import logging

from devildex.models import PackageDetails

logger = logging.getLogger(__name__)
PART_LENGTH = 2


def get_installed_packages_with_project_urls(explicit: set | None = None) -> list:
    """Return a list of PackageDetails objects for all installed packages.

    (or for those explicitly specified), including name, version
    and a dictionary of their Project-URL.
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
                        logger.warning(
                            "ATTENTION: impossible to analyze the project-url item for "
                            f"{package_name}: '{url_entry}'"
                        )
                except AttributeError:
                    logger.warning(
                        "AttributeError while parsing Project-URL item "
                        f"'{url_entry}' "
                        f"for {package_name}. Expected string parts. Error",
                        exc_info=True,
                    )
                except RuntimeError:
                    logger.exception(
                        f"Runtime error parsing Project-URL item '{url_entry}' "
                        f"for {package_name}"
                    )

        pkg_details = PackageDetails(
            name=package_name,
            version=package_version,
            project_urls=current_project_urls,
        )
        package_list.append(pkg_details)

    return package_list
