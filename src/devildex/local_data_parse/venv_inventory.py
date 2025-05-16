"""venv inventory module."""

import importlib.metadata


def get_installed_packages_with_docs_urls(explicit=None):
    """Return a list for all packages installed that declares a documentation URL."""
    package_list = []
    for dist in importlib.metadata.distributions():
        if explicit and dist.name not in explicit:
            continue
        package_name = dist.name
        package_version = dist.version
        docs_url = None
        metadata = dist.metadata

        if metadata.get_all("Project-URL"):
            for url_entry in metadata.get_all("Project-URL"):
                if "Documentation" in url_entry:
                    parts = url_entry.split(",", 1)
                    if len(parts) == 2:
                        docs_url = parts[1].strip()
                        break

        package_list.append(
            {"name": package_name, "version": package_version, "docs_url": docs_url}
        )

    return package_list


if __name__ == "__main__":

    installed_docs_info = get_installed_packages_with_docs_urls()

    print("Packages Python installed con URL di documentation:")
    for pkg_info in installed_docs_info:
        d_url = pkg_info['docs_url']
        print(
            f"  - {pkg_info['name']} ({pkg_info['version']}): "
            f"{(d_url if d_url else 'URL documentation non trovato')}"
        )
