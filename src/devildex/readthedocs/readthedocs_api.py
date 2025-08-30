"""readthedocs api module."""

import logging
import os
from json import JSONDecodeError
from pathlib import Path

import requests

FILENAME_MAX_LENGTH = 60

logger = logging.getLogger(__name__)


def _fetch_available_versions(project_slug: str) -> list[dict] | None:
    """Fetch ALL available versions for a project from RTD API, handling pagination."""
    all_versions_results = []
    next_page_url = f"https://readthedocs.org/api/v3/projects/{project_slug}/versions/"
    logger.info(f"\nCalling API to list versions (starting with): {next_page_url}")

    page_num = 1
    while next_page_url:
        try:
            logger.info(f"Fetching page {page_num} from: {next_page_url}")
            response = requests.get(next_page_url, timeout=30)
            response.raise_for_status()
            data = response.json()

            current_page_versions = data.get("results", [])
            all_versions_results.extend(current_page_versions)

            total_count = data.get("count", len(all_versions_results))

            logger.info(
                f"Page {page_num}: Fetched {len(current_page_versions)} versions. "
                f"Total fetched so far: {len(all_versions_results)}"
                f"out of {total_count}."
            )

            next_page_url = data.get("next")
            page_num += 1

        except requests.exceptions.RequestException:
            logger.exception(f"Error calling API list versions ({next_page_url})")
            return None
        except JSONDecodeError:
            logger.exception(
                f"Error decoding JSON response while listing versions "
                f"({next_page_url})"
            )
            return None

    logger.info(
        "API list versions: All pages fetched. Total versions found:"
        f" {len(all_versions_results)}."
    )
    return all_versions_results


def _choose_best_version(
    available_versions: list[dict], preferred_versions: list[str]
) -> str | None:
    """Choose the slug of the best version of those available."""
    if not available_versions:
        logger.error("Error: No versions available for choice (list is empty or None).")
        return None

    logger.info(
        f"\nAnalyzing {len(available_versions)} available versions to choose the best:"
    )

    for preferred_slug in preferred_versions:
        for version in available_versions:
            if (
                version.get("slug") == preferred_slug
                and version.get("active") is True
                and version.get("built") is True
            ):
                logger.info(
                    f"\nChosen favourite version (active and built): '{preferred_slug}'"
                )
                return preferred_slug

    logger.info(
        "\nNo favourite version found (active and built). "
        "Searching for the first available active and built version..."
    )
    for version in available_versions:
        if version.get("active") is True and version.get("built") is True:
            chosen_slug = version.get("slug")
            logger.info(
                "Chosen first available (active and built) version:" f" '{chosen_slug}'"
            )
            return chosen_slug

    logger.error("\nError: No active and built version found among all available ones.")
    return None


def _fetch_version_details(project_slug: str, version_slug: str) -> dict | None:
    """Fetch a specific version details from RTD API."""
    api_version_detail_url = f"https://readthedocs.org/api/v3/versions/{version_slug}/"
    logger.info(
        f"\nCalling API fo version details '{version_slug}': "
        f"{api_version_detail_url} con project__slug={project_slug}"
    )
    try:
        response = requests.get(
            api_version_detail_url, params={"project__slug": project_slug}, timeout=60
        )
        response.raise_for_status()
        version_detail_data = response.json()
        logger.info(f"API details version called successfully for '{version_slug}'.")

    except requests.exceptions.RequestException:
        logger.exception(
            f"Error calling API details version ({api_version_detail_url}?"
            f"project__slug={project_slug})"
        )
        return None
    except JSONDecodeError:
        logger.exception(
            f"Error decoding JSON response for version details "
            f"({api_version_detail_url}?project__slug={project_slug})"
        )
        return None
    else:
        return version_detail_data


def _get_download_url(version_details: dict, download_format: str) -> str | None:
    """Extract download URL for specific format from version details."""
    if not version_details:
        logger.error(
            "Error: version details not available to search for the download URL."
        )
        return None

    download_urls = version_details.get("downloads")
    if not download_urls:
        version_slug = version_details.get("slug", "unknown")
        logger.error(
            f"Error: 'downloads' field not found in version details for  "
            f"'{version_slug}'."
        )
        logger.error("Ensure that offline formats are enabled for this version.")
        return None

    file_url = download_urls.get(download_format)
    if not file_url:
        version_slug = version_details.get("slug", "unknown")
        logger.error(
            f"Error: Format '{download_format}' non disponibile per la version "
            f"'{version_slug}'."
        )
        logger.info(f"Formats available: {list(download_urls.keys())}")
        return None

    if file_url.startswith("//"):
        file_url = "https:" + file_url

    if not file_url.lower().endswith((".zip", ".pdf", ".epub")):
        logger.warning(
            f"Warning: found URL '{file_url}' may not be a direct link "
            "to downloadable file (extension not detected). "
            "Proceeding anyway..."
        )

    logger.info(
        f"\nURL found for {download_format} version "
        f"'{version_details.get('slug', 'unknown')}': {file_url}"
    )
    return file_url


def _determine_local_filename(
    project_slug: str, version_slug: str, download_url: str, download_format: str
) -> str:
    """Determine local file name which makes sense for download."""
    file_extension = download_format.replace("htmlzip", "zip")
    basename_with_query = download_url.split("/")[-1]
    filename_from_url = basename_with_query.split("?")[0]

    if "." in filename_from_url and len(filename_from_url) <= FILENAME_MAX_LENGTH:
        local_filename = filename_from_url
    else:
        local_filename = f"{project_slug}-{version_slug}.{file_extension}"

    return local_filename


def _download_file(file_url: str, local_filepath: Path) -> bool | None:
    """Download file from URL into a local path."""
    logger.info(f"Download file in: {local_filepath}")
    download_successful = False
    try:
        with requests.get(file_url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(local_filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"Download completed: {local_filepath}")
        download_successful = True
    except (OSError, requests.exceptions.RequestException):
        logger.exception(f"Error during file download ({file_url})")
        if os.path.exists(local_filepath):
            try:
                os.remove(local_filepath)
                logger.info(f"partial File removed: {local_filepath}")
            except OSError:
                logger.exception("Error while removing partial file")
        return False
    else:
        return True
    finally:
        if not download_successful and os.path.exists(local_filepath):
            try:
                os.remove(local_filepath)
                logger.info(f"partial File removed: {local_filepath}")
            except OSError:
                logger.exception("Error while removing partial file")


def download_readthedocs_prebuilt_robust(
    project_name: str,
    download_folder: str = "rtd_prebuilt_downloads",
    preferred_versions: tuple[str] = ("stable", "latest"),
    download_format: str = "htmlzip",
) -> str | None:
    """Download a pre-packaged documentation from Read the Docs.

    Args:
        project_name (str): project name (used as slug).
        download_folder: download folder
        preferred_versions (list): versions slugs list to
            prefer (in order).
        download_format (str): Il format to download (es. 'htmlzip', 'pdf', 'epub').

    Returns:
        str: Il path downloaded file, o None in caso di failure.

    """
    final_downloaded_path = None

    project_slug = project_name
    if not project_slug:
        logger.error("Error: project_slug is empty. Cannot proceed with download.")
        return None

    available_versions = _fetch_available_versions(project_slug)
    if available_versions is None:
        return None

    chosen_version_slug = _choose_best_version(
        available_versions, list(preferred_versions)
    )
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
    local_filepath = Path(download_folder) / local_filename

    if _download_file(file_url, local_filepath):
        final_downloaded_path = local_filepath

    return final_downloaded_path


if __name__ == "__main__":  # pragma: no cover
    logger.info("--- Executing Script: Download Prebuilt Docs (Robust) ---")

    logger.info("\nTrying with: Black (https://black.readthedocs.io/)")
    downloaded_file_black = download_readthedocs_prebuilt_robust(project_name="black")
    if downloaded_file_black:
        logger.info(f"  SUCCESS: Downloaded for Black: {downloaded_file_black}")
    else:
        logger.error("  FAILURE: Download failed for Black.")
    logger.info("-" * 30)

    logger.info("\nTrying with: Requests (https://requests.readthedocs.io/)")
    downloaded_file_requests = download_readthedocs_prebuilt_robust(
        project_name="requests"
    )
    if downloaded_file_requests:
        logger.info(f"  SUCCESS: Downloaded for Requests: {downloaded_file_requests}")
    else:
        logger.error("  FAILURE: Download failed for Requests.")
    logger.info("-" * 30)

    logger.info("\nTrying with: Sphinx (https://sphinx.readthedocs.io/)")
    downloaded_file_sphinx = download_readthedocs_prebuilt_robust(
        project_name="sphinx-doc"
    )
    if downloaded_file_sphinx:
        logger.info(f"  SUCCESS: Downloaded for Sphinx: {downloaded_file_sphinx}")
    else:
        logger.error("  FAILURE: Download failed for Sphinx.")
    logger.info("-" * 30)

