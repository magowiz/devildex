"""readthedocs api module."""

import os
from urllib.parse import urlparse

import requests




def _fetch_available_versions(project_slug):
    """Fetch ALL available versions for a project from RTD API, handling pagination."""
    all_versions_results = []
    next_page_url = (
        f"https://readthedocs.org/api/v3/projects/{project_slug}/versions/"
    )
    print(f"\nCalling API to list versions (starting with): {next_page_url}")

    page_num = 1
    while next_page_url:
        try:
            print(f"Fetching page {page_num} from: {next_page_url}")
            response = requests.get(next_page_url, timeout=30)
            response.raise_for_status()
            data = response.json()

            current_page_versions = data.get("results", [])
            all_versions_results.extend(current_page_versions)

            total_count = data.get('count', len(all_versions_results))

            print(
                f"Page {page_num}: Fetched {len(current_page_versions)} versions. "
                f"Total fetched so far: {len(all_versions_results)} out of {total_count}."
            )

            next_page_url = data.get("next")
            page_num += 1
            if next_page_url:
                pass

        except requests.exceptions.RequestException as e:
            print(f"Error calling API list versions ({next_page_url}): {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while listing versions: {e}")
            return None

    print(
        f"API list versions: All pages fetched. Total versions found: {len(all_versions_results)}."
    )
    return all_versions_results


def _choose_best_version(available_versions, preferred_versions):
    """Sceglie lo slug della versione migliore tra quelle disponibili."""
    if not available_versions:
        print("Error: No versions available for choice (list is empty or None).")
        return None

    print(f"\nAnalyzing {len(available_versions)} available versions to choose the best:")

    for preferred_slug in preferred_versions:
        for version in available_versions:
            if (
                version.get("slug") == preferred_slug
                and version.get("active") is True
                and version.get("built") is True
            ):
                print(f"\nChosen favourite version (active and built): '{preferred_slug}'")
                return preferred_slug

    print(
        "\nNo favourite version found (active and built). "
        "Searching for the first available active and built version..."
    )
    for version in available_versions:
        if version.get("active") is True and version.get("built") is True:
            chosen_slug = version.get("slug")
            print(f"Chosen first available (active and built) version: '{chosen_slug}'")
            return chosen_slug

    print("\nError: No active and built version found among all available ones.")
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
            api_version_detail_url, params={"project__slug": project_slug}, timeout=60
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
    download_successful = False
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        with requests.get(file_url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(local_filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Download completed: {local_filepath}")
        download_successful = True
        return True
    except (requests.exceptions.RequestException, IOError) as e:
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
    finally:
        if not download_successful and os.path.exists(local_filepath):
            try:
                os.remove(local_filepath)
                print(f"partial File removed: {local_filepath}")
            except OSError as remove_err:
                print(f"Error while removing partial file: {remove_err}")


def download_readthedocs_prebuilt_robust(project_name,
    rtd_url, download_folder="rtd_prebuilt_downloads",
        preferred_versions=("stable", "latest"), download_format="htmlzip"
):
    """Download a pre-packaged documentation from Read the Docs.

    Args:
        project_name (str): project name.
        rtd_url (str): project base URL of Read the Docs
            (es. https://black.readthedocs.io/).
        preferred_versions (list): versions slugs list to
            prefer (in order).
        download_format (str): Il format to download (es. 'htmlzip', 'pdf', 'epub').

    Returns:
        str: Il path downloaded file, o None in caso di failure.
    """
    project_slug = project_name
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
    output_dir = download_folder
    os.makedirs(output_dir, exist_ok=True)
    local_filepath = os.path.join(output_dir, local_filename)

    if _download_file(file_url, local_filepath):
        return local_filepath
    return None

if __name__ == "__main__":
    print("--- Executing Script: Download Prebuilt Docs (Robust) ---") # Titolo più generico

    print("\nTrying with: Black (https://black.readthedocs.io/)")
    downloaded_file_black = download_readthedocs_prebuilt_robust(
        project_name="black",
        rtd_url="https://black.readthedocs.io/"
    )
    if downloaded_file_black:
        print(f"  SUCCESS: Downloaded for Black: {downloaded_file_black}")
    else:
        print("  FAILURE: Download failed for Black.")
    print("-" * 30)

    print("\nTrying with: Requests (https://requests.readthedocs.io/)")
    downloaded_file_requests = download_readthedocs_prebuilt_robust(
        project_name="requests",
        rtd_url="https://requests.readthedocs.io/"
    )
    if downloaded_file_requests:
        print(f"  SUCCESS: Downloaded for Requests: {downloaded_file_requests}")
    else:
        print("  FAILURE: Download failed for Requests.")
    print("-" * 30)

    print("\nTrying with: Sphinx (https://sphinx.readthedocs.io/)")
    downloaded_file_sphinx = download_readthedocs_prebuilt_robust(
        project_name="sphinx-doc",
        rtd_url="https://sphinx.readthedocs.io/"
    )
    if downloaded_file_sphinx:
        print(f"  SUCCESS: Downloaded for Sphinx: {downloaded_file_sphinx}")
    else:
        print("  FAILURE: Download failed for Sphinx.")
    print("-" * 30)
