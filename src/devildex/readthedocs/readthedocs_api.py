import os
from urllib.parse import urlparse

import requests


def _get_project_slug(rtd_url):
    """Extract Read the Docs project slug from an URL."""
    print(f"Analyzing the URL: {rtd_url}")
    parsed_url = urlparse(rtd_url)
    path_parts = [part for part in parsed_url.path.split("/") if part]
    project_slug = parsed_url.hostname.split(".")[0]

    if project_slug == "readthedocs" and path_parts:
        project_slug = path_parts[0]
    elif not project_slug or project_slug == "www" or project_slug == "readthedocs":
        if path_parts:
            project_slug = path_parts[0]
        else:
            print("Error: Unable to deduct slug del project from URL.")
            return None

    print(f"project Slug deduct: {project_slug}")
    return project_slug


def _fetch_available_versions(project_slug):
    """Fetch available versions for a project from RTD API."""
    api_list_versions_url = (
        f"https://readthedocs.org/api/v3/projects/{project_slug}/versions/"
    )
    print(f"\nCalling API to list versions: {api_list_versions_url}")
    try:
        response = requests.get(api_list_versions_url)
        response.raise_for_status()
        versions_list_data = response.json()
        print(
            "API list versions called successfully. Found "
            f"{versions_list_data.get('count', 'N/A')} versions."
        )
        return versions_list_data.get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"Error calling API list versions ({api_list_versions_url}): {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while listing versions: {e}")
        return None


def _choose_best_version(available_versions, preferred_versions):
    """Sceglie lo slug della versione migliore tra quelle disponibili."""
    if not available_versions:
        print("Error: No version available given for choice.")
        return None

    print("Available Versions (slug, active, built):")
    for version in available_versions:
        print(
            f"- {version.get('slug')}: Active={version.get('active')}, "
            f"Built={version.get('built')}"
        )

    for preferred in preferred_versions:
        for version in available_versions:
            if (
                version.get("slug") == preferred
                and version.get("active")
                and version.get("built")
            ):
                print(f"\nChosen favourite version and available: '{preferred}'")
                return preferred

    print(
        "\nNo favourite version available (active and built). Trying to download "
        "first available active and built found."
    )
    for version in available_versions:
        if version.get("active") and version.get("built"):
            chosen_slug = version.get("slug")
            print(f"Chosen first version active and built: '{chosen_slug}'")
            return chosen_slug

    print(
        "\nError: No active and built version found between available ones."
    )
    return None


def _fetch_version_details(project_slug, version_slug):
    """Fetch a specific version details from RTD API."""
    api_version_detail_url = f"https://readthedocs.org/api/v3/versions/{version_slug}/"
    print(
        f"\nCalling API fo version details '{version_slug}': "
        f"{api_version_detail_url} con project__slug={project_slug}"
    )
    try:
        response = requests.get(
            api_version_detail_url, params={"project__slug": project_slug}
        )
        response.raise_for_status()
        version_detail_data = response.json()
        print(f"API details version called successfully for '{version_slug}'.")
        return version_detail_data
    except requests.exceptions.RequestException as e:
        print(
            f"Error calling API details version ({api_version_detail_url}?"
            f"project__slug={project_slug}): {e}"
        )
        return None
    except Exception as e:
        print("An unexpected error occurred getting details " f"of version: {e}")
        return None


def _get_download_url(version_details, download_format):
    """Extract download URL for specific format from version details."""
    if not version_details:
        print("Error: version details not available to search for the download URL.")
        return None

    download_urls = version_details.get("downloads")
    if not download_urls:
        version_slug = version_details.get("slug", "unknown")
        print(
            f"Error: 'downloads' field not found in version details for  "
            f"'{version_slug}'."
        )
        print("Ensure that offline formats are enabled for this version.")
        return None

    file_url = download_urls.get(download_format)
    if not file_url:
        version_slug = version_details.get("slug", "unknown")
        print(
            f"Error: Format '{download_format}' non disponibile per la version "
            f"'{version_slug}'."
        )
        print(f"Formats available: {list(download_urls.keys())}")
        return None

    if file_url.startswith("//"):
        file_url = "https:" + file_url

    if not file_url.lower().endswith((".zip", ".pdf", ".epub")):
        print(
            f"Warning: found URL '{file_url}' may not be a direct link "
            "to downloadable file (extension not detected). "
            "Proceeding anyway..."
        )

    print(
        f"\nURL found for {download_format} version "
        f"'{version_details.get('slug', 'unknown')}': {file_url}"
    )
    return file_url


def _determine_local_filename(
    project_slug, version_slug, download_url, download_format
):
    """Determine local file name which makes sense for download."""
    file_extension = download_format.replace("htmlzip", "zip")
    filename_from_url = download_url.split("/")[-1]

    if "." in filename_from_url and len(filename_from_url) <= 60:
        local_filename = filename_from_url
    else:
        local_filename = f"{project_slug}-{version_slug}.{file_extension}"

    return local_filename


def _download_file(file_url, local_filepath):
    """Download file from URL into a local path."""
    print(f"Download file in: {local_filepath}")
    try:
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            with open(local_filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Download completed: {local_filepath}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error during file download ({file_url}): {e}")
        if os.path.exists(local_filepath):
            try:
                os.remove(local_filepath)
                print(f"partial File removed: {local_filepath}")
            except OSError as remove_err:
                print(f"Error while removing partial file: {remove_err}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during file download: {e}")
        return False


def download_readthedocs_prebuilt_robust(
    rtd_url, preferred_versions=["stable", "latest"], download_format="htmlzip"
):
    """
    Download a pre-packaged documentation version from Read the Docs
    using functions helpers for better clarity and maintainability.

    Args:
        rtd_url (str): project base URL of Read the Docs
            (es. https://black.readthedocs.io/).
        preferred_versions (list): versions slugs list to
            prefer (in order).
        download_format (str): Il format to download (es. 'htmlzip', 'pdf', 'epub').

    Returns:
        str: Il path downloaded file, o None in caso di failure.
    """
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


print("--- Executing Script 1 (Version 3: Robusta - Refactored) ---")

print("Trying with: https://black.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://black.readthedocs.io/")
if downloaded_file:
    print(f"successfully Downloaded for Black: {downloaded_file}")
else:
    print("failed Download for Black.")
print("-" * 30)

print("Trying with: https://requests.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust(
    "https://requests.readthedocs.io/"
)
if downloaded_file:
    print(f"Download successfully for Requests: {downloaded_file}")
else:
    print("Failed Download per Requests.")
print("-" * 30)

print("Trying with: https://sphinx.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://sphinx.readthedocs.io/")
if downloaded_file:
    print(f"Download successfully for Sphinx: {downloaded_file}")
else:
    print("Failed Download for Sphinx.")
print("-" * 30)

print("--- Executing Script 1 (Version 3: Robusta) ---")

print("Trying with: https://black.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://black.readthedocs.io/")
if downloaded_file:
    print(f"Download successo per Black: {downloaded_file}")
else:
    print("Download failed for Black.")
print("-" * 30)

print("Trying with: https://requests.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust(
    "https://requests.readthedocs.io/"
)
if downloaded_file:
    print(f"Download successfully for Requests: {downloaded_file}")
else:
    print("Download failed for Requests.")
print("-" * 30)

print("Trying with: https://sphinx.readthedocs.io/")
downloaded_file = download_readthedocs_prebuilt_robust("https://sphinx.readthedocs.io/")
if downloaded_file:
    print(f"Download successfully for Sphinx: {downloaded_file}")
else:
    print("Failed Download for Sphinx.")
print("-" * 30)
