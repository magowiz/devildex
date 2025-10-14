import logging
import os
import shutil
from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING

import requests

from devildex.grabbers.abstract_grabber import AbstractGrabber

if TYPE_CHECKING:
    from devildex.orchestrator.build_context import BuildContext

logger = logging.getLogger(__name__)

FILENAME_MAX_LENGTH = 60


class ReadTheDocsDownloader(AbstractGrabber):
    """Grabber for downloading pre-built documentation from Read the Docs."""

    def generate_docset(self, source_path: Path, output_path: Path, context: "BuildContext") -> bool:
        """Downloads a pre-packaged documentation from Read the Docs.

        :param source_path: Not used for ReadTheDocsDownloader, but required by AbstractGrabber.
        :param output_path: The path where the downloaded documentation should be stored.
        :param context: The build context containing necessary information for the download process.
                        Expected to contain project_slug, version_identifier, and download_format.
        :return: True if documentation download was successful, False otherwise.
        """
        project_slug = context.project_slug
        version_identifier = context.version_identifier
        download_format = context.download_format if hasattr(context, 'download_format') else "htmlzip" # Default to htmlzip

        if not project_slug:
            logger.error("Error: project_slug is empty in BuildContext. Cannot proceed with download.")
            return False

        # Use version_identifier from context as preferred version
        preferred_versions = [version_identifier] if version_identifier else ["stable", "latest"]

        available_versions = self._fetch_available_versions(project_slug)
        if available_versions is None:
            return False

        chosen_version_slug = self._choose_best_version(
            available_versions, preferred_versions
        )
        if not chosen_version_slug:
            return False

        version_details = self._fetch_version_details(project_slug, chosen_version_slug)
        if not version_details:
            return False

        file_url = self._get_download_url(version_details, download_format)
        if not file_url:
            return False

        local_filename = self._determine_local_filename(
            project_slug, chosen_version_slug, file_url, download_format
        )

        # Ensure output_path exists
        output_path.mkdir(parents=True, exist_ok=True)
        local_filepath = output_path / local_filename

        if self._download_file(file_url, local_filepath):
            # If it's a zip file, extract it
            if download_format == "htmlzip" and local_filepath.suffix == ".zip":
                extract_dir = output_path / f"{project_slug}-{chosen_version_slug}"
                try:
                    shutil.unpack_archive(local_filepath, extract_dir)
                    logger.info(f"Extracted {local_filepath} to {extract_dir}")
                    # Remove the zip file after extraction
                    local_filepath.unlink()
                    return True
                except shutil.ReadError:
                    logger.exception(f"Error extracting archive {local_filepath}")
                    return False
            return True
        return False

    def can_handle(self, source_path: Path, context: "BuildContext") -> bool:
        """Determines if this grabber can handle the project.
        For ReadTheDocsDownloader, it can handle if the doc_type in context is 'readthedocs'.
        """
        return context.doc_type == "readthedocs"

    def _fetch_available_versions(self, project_slug: str) -> list[dict] | None:
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
        self, available_versions: list[dict], preferred_versions: list[str]
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

    def _fetch_version_details(self, project_slug: str, version_slug: str) -> dict | None:
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

    def _get_download_url(self, version_details: dict, download_format: str) -> str | None:
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
        self, project_slug: str, version_slug: str, download_url: str, download_format: str
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

    def _download_file(self, file_url: str, local_filepath: Path) -> bool:
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
