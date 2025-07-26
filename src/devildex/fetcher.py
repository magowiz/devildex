"""fetching module."""

import json
import logging
import pathlib
import re
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class MissingPackageInfoError(ValueError):
    """Custom exception for when package name or version is missing."""

    def __init__(self) -> None:
        """Construct a MissingPackageInfoError object."""
        super().__init__(
            "Name of the package and Version must be provided in package_info_dict."
        )


class PackageSourceFetcher:
    """Class that implement fetching mechanisms for packages."""

    def __init__(self, base_save_path: str, package_info_dict: dict) -> None:
        """Construct a PackageSourceFetcher object."""
        self.base_save_path = pathlib.Path(base_save_path)

        self.package_name = package_info_dict.get("name")
        self.package_version = package_info_dict.get("version")
        self.project_urls = package_info_dict.get("project_urls", {})

        if not self.package_name or not self.package_version:
            raise MissingPackageInfoError()

        sane_pkg_name = self._sanitize_path_component(self.package_name)
        sane_pkg_version = self._sanitize_path_component(self.package_version)

        self.download_target_path = (
            self.base_save_path / sane_pkg_name / sane_pkg_version
        )

        self._determined_vcs_url: str | None = None

    @staticmethod
    def _sanitize_path_component(name: str) -> str:
        if not name:
            return "unknown_component"
        name = re.sub(r'[<>:"/\\|?*\s]+', "_", name)
        name = re.sub(r"_+", "_", name)
        name = name.strip("_")
        if not name:
            return "sanitized_empty_component"
        return name

    def _ensure_target_dir_exists(self) -> bool:
        try:
            self.download_target_path.mkdir(parents=True, exist_ok=True)
            logger.info(
                f"Destination Directory Insured/Created:{self.download_target_path}"
            )

        except OSError:
            return False
        else:
            return True

    def _cleanup_target_dir_content(self) -> None:
        if not self.download_target_path.exists():
            return
        logger.info(
            "Cleaning content of target directory: " f"{self.download_target_path}"
        )
        try:
            for item in self.download_target_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        except OSError:
            logger.exception(
                "Error during cleaning directory " f"{self.download_target_path}"
            )

    def _fetch_project_urls_from_pypi(self) -> dict | None:
        """Fetch project_urls from PyPI JSON API for the current package."""
        logger.info(
            "Attempted fetch of the project_urls from Pypi Json API for "
            f"{self.package_name}."
        )

        try:
            api_url = (
                f"https://pypi.org/pypi/{self.package_name}"
                f"/{self.package_version}/json"
            )
            response = requests.get(api_url, timeout=15)
            response.raise_for_status()
            pypi_data = response.json()
            fetched_pypi_urls = pypi_data.get("info", {}).get("project_urls", {})
            if fetched_pypi_urls:
                return fetched_pypi_urls
        except requests.RequestException:
            pass
        except json.JSONDecodeError:
            pass
        return None

    def _find_vcs_url_in_dict(
        self, urls_dict: dict | None, source_description: str
    ) -> str | None:
        """Search for a valid VCS URL within a dictionary of URLs."""
        if not urls_dict:
            return None

        preferred_labels = ["Source Code", "Source", "Repository", "Homepage"]
        for label in preferred_labels:
            url = urls_dict.get(label)
            if url and self._is_valid_vcs_url(url):
                logger.info(
                    f"URL VCS determined ({label} from {source_description}): {url}"
                )
                return url
        return None

    def _get_vcs_url(self) -> str | None:
        if self._determined_vcs_url is not None:
            return self._determined_vcs_url
        vcs_url = self._find_vcs_url_in_dict(self.project_urls, "local")
        if vcs_url:
            self._determined_vcs_url = vcs_url
            return vcs_url

        pypi_urls = self._fetch_project_urls_from_pypi()
        vcs_url = self._find_vcs_url_in_dict(pypi_urls, "PyPI API")
        if vcs_url:
            self._determined_vcs_url = vcs_url
            return vcs_url
        self._determined_vcs_url = ""
        return None

    @staticmethod
    def _is_valid_vcs_url(url: str) -> bool:
        if not url or not isinstance(url, str):  # Added type check
            return False
        return any(
            host in url for host in ["github.com", "gitlab.com", "bitbucket.org"]
        ) or url.endswith(".git")

    @staticmethod
    def _is_path_safe(base_dir_abs: Path, target_path_abs: Path) -> bool:
        """Check if target_path_abs is safely within base_dir_abs."""
        try:
            return target_path_abs.resolve().is_relative_to(base_dir_abs.resolve())
        except (ValueError, OSError):
            return False

    @staticmethod
    def _is_member_name_safe(member_name: str) -> bool:
        """Check if member name is safe (no '..' or absolute paths).

        This check correctly depends on the OS where the code is running.
        pathlib.Path.is_absolute() correctly identifies absolute paths
        for the current platform (e.g., /... on Linux, C:\\... on Windows).
        """
        # A path traversal attempt is always unsafe on any platform.
        if ".." in member_name:
            return False

        # An absolute path is unsafe if it's considered absolute by the
        # current operating system.
        return not pathlib.Path(member_name).is_absolute()

    @staticmethod
    def _extract_zip_safely(
        archive_filename: pathlib.Path, temp_extract_dir_abs: Path
    ) -> bool:
        try:
            with zipfile.ZipFile(archive_filename, "r") as zip_ref:
                for member_info in zip_ref.infolist():
                    if not PackageSourceFetcher._is_member_name_safe(
                        member_info.filename
                    ):
                        return False

                    member_dest_path = temp_extract_dir_abs / member_info.filename
                    if not PackageSourceFetcher._is_path_safe(
                        temp_extract_dir_abs, member_dest_path.resolve()
                    ):
                        return False

                    if not member_info.is_dir():
                        member_dest_path.parent.mkdir(parents=True, exist_ok=True)
                        zip_ref.extract(member_info, path=temp_extract_dir_abs)
                    else:
                        member_dest_path.mkdir(parents=True, exist_ok=True)

        except (zipfile.BadZipFile, OSError):
            return False
        else:
            return True

    @staticmethod
    def _extract_tar_safely(
        archive_filename: pathlib.Path, temp_extract_dir_abs: Path
    ) -> bool:
        try:
            with tarfile.open(archive_filename, "r:*") as tar_ref:
                for member in tar_ref.getmembers():
                    if not PackageSourceFetcher._is_member_name_safe(member.name):
                        return False  # Error logged by helper

                    member_dest_path = temp_extract_dir_abs / member.name
                    if not PackageSourceFetcher._is_path_safe(
                        temp_extract_dir_abs, member_dest_path.resolve()
                    ):
                        return False

                    if member.isfile() or member.isdir():
                        tar_ref.extract(
                            member, path=temp_extract_dir_abs, set_attrs=False
                        )
        except tarfile.TarError:
            return False
        else:
            return True

    @staticmethod
    def _extract_archive(
        archive_filename: pathlib.Path, temp_extract_dir: Path
    ) -> bool:
        temp_extract_dir_abs = temp_extract_dir.resolve()
        success = False

        if str(archive_filename).lower().endswith(".zip"):
            success = PackageSourceFetcher._extract_zip_safely(
                archive_filename, temp_extract_dir_abs
            )
        elif (
            str(archive_filename)
            .lower()
            .endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar"))
        ):
            success = PackageSourceFetcher._extract_tar_safely(
                archive_filename, temp_extract_dir_abs
            )

        return success

    @staticmethod
    def _download_file(filename: Path, url: str) -> None:
        filename.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    @staticmethod
    def _determine_content_source_dir(temp_extract_dir: Path) -> Path | None:
        """Determine the correct source directory within the extracted content."""
        extracted_items = list(temp_extract_dir.iterdir())
        if not extracted_items:
            return None

        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            content_source_dir = extracted_items[0]
        else:
            content_source_dir = temp_extract_dir
        return content_source_dir

    @staticmethod
    def _move_extracted_content(source_dir: Path, destination_dir: Path) -> bool:
        """Move content from source_dir to destination_dir."""
        try:
            for item in source_dir.iterdir():
                destination_item_path = destination_dir / item.name
                shutil.move(str(item), str(destination_item_path))

        except OSError:
            return False
        else:
            return True

    def _download_and_extract_archive(
        self, url: str, temp_base_dir: pathlib.Path
    ) -> bool:
        archive_filename = temp_base_dir / url.split("/")[-1].split("?")[0]
        temp_extract_dir = temp_base_dir / "extracted_content"

        operation_successful = False
        try:
            if temp_base_dir.exists():
                shutil.rmtree(temp_base_dir)
            temp_base_dir.mkdir(parents=True, exist_ok=True)
            PackageSourceFetcher._download_file(archive_filename, url)
            temp_extract_dir.mkdir(parents=True, exist_ok=True)
            if not self._extract_archive(archive_filename, temp_extract_dir):
                return False

            content_source_dir = self._determine_content_source_dir(temp_extract_dir)
            if not content_source_dir:
                return False

            self._cleanup_target_dir_content()
            if not self._ensure_target_dir_exists():
                return False

            if self._move_extracted_content(
                content_source_dir, self.download_target_path
            ):
                operation_successful = True

        except requests.RequestException:
            pass
        finally:
            if temp_base_dir.exists():
                shutil.rmtree(temp_base_dir)

        return operation_successful

    @staticmethod
    def _run_git_command(
        command_list: list[str],
        cwd: pathlib.Path | None = None,
        check_errors: bool = True,
    ) -> subprocess.CompletedProcess | None:
        try:
            git_exe = shutil.which("git")
            if not git_exe:
                return None

            actual_command = (
                [git_exe] + command_list[1:]
                if command_list[0] == "git"
                else [git_exe, *command_list]
            )

            process = subprocess.run(  # noqa: S603
                actual_command,
                capture_output=True,
                text=True,
                check=check_errors,
                cwd=cwd,
                encoding="utf-8",
                errors="replace",
            )
            if process.stdout:
                logger.debug(f"Git stdout:\n{process.stdout.strip()}")
            if process.stderr and process.returncode != 0:
                logger.warning(f"Git stderr:\n{process.stderr.strip()}")
            elif process.stderr:
                logger.debug(f"Git stderr (info):\n{process.stderr.strip()}")

        except subprocess.CalledProcessError:
            pass
        else:
            return process
        return None

    @staticmethod
    def _cleanup_git_dir_from_path(path_to_clean: pathlib.Path) -> bool:
        git_dir = path_to_clean / ".git"
        if git_dir.is_dir():
            try:
                shutil.rmtree(git_dir)

            except OSError:
                return False
            else:
                return True
        elif git_dir.exists():
            return False
        return True

    def _fetch_from_pypi(self) -> bool:
        api_url = (
            f"https://pypi.org/pypi/{self.package_name}/{self.package_version}/json"
        )
        try:
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            sdist_url = next(
                (
                    release_file["url"]
                    for release_file in data.get("urls", [])
                    if release_file.get("packagetype") == "sdist"
                ),
                None,
            )

            if not sdist_url:
                return False
            logger.info(f"Trovato URL sdist: {sdist_url}")
            temp_dir_for_pypi = (
                self.base_save_path
                / f"{self._sanitize_path_component(self.package_name)}_temp_dl"
                / "pypi_sdist"
            )
            if self._download_and_extract_archive(sdist_url, temp_dir_for_pypi):
                return True
        except requests.RequestException:
            pass
        except json.JSONDecodeError:
            pass
        return False

    def _try_fetch_tag_github_archive(
        self, repo_url: str, tag_variations: list[str]
    ) -> bool:
        """Attempt to download and extract a tag archive directly from GitHub."""
        if "github.com" not in repo_url:
            return False

        repo_path_segment = repo_url.split("github.com/")[-1].replace(".git", "")
        for tag in tag_variations:
            tag_for_url = tag.replace("refs/tags/", "")
            archive_urls_to_try = [
                f"https://github.com/{repo_path_segment}/archive/"
                f"refs/tags/{tag_for_url}.tar.gz",
                f"https://github.com/{repo_path_segment}/archive/"
                f"refs/tags/{tag_for_url}.zip",
                f"https://github.com/{repo_path_segment}/archive/"
                f"{tag_for_url}.tar.gz",
                f"https://github.com/{repo_path_segment}/archive/{tag_for_url}.zip",
            ]
            for archive_url in archive_urls_to_try:
                temp_dir_for_archive_download = (
                    self.base_save_path
                    / f"{self._sanitize_path_component(self.package_name)}_temp_dl"
                    / "github_archive"
                )
                if self._download_and_extract_archive(
                    archive_url, temp_dir_for_archive_download
                ):
                    return True
        return False

    def _try_fetch_tag_shallow_clone(
        self, repo_url: str, tag_variations: list[str]
    ) -> bool:
        """Attempt to fetch a tag using a shallow git clone."""
        for tag in tag_variations:
            self._cleanup_target_dir_content()
            if not self._ensure_target_dir_exists():
                continue

            if self._run_git_command(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    tag,
                    repo_url,
                    str(self.download_target_path),
                ]
            ):
                self._cleanup_git_dir_from_path(self.download_target_path)
                logger.info(
                    f"Clone of tag '{tag}' succeeded in {self.download_target_path}."
                )
                return True
        return False

    @staticmethod
    def _copy_cloned_content(source_dir: Path, destination_dir: Path) -> bool:
        """Copy content from source_dir to destination_dir, excluding .git.

        Assumes destination_dir is clean and exists.
        """
        try:
            for item in source_dir.iterdir():
                if item.name == ".git":
                    continue
                target_item_path = destination_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, target_item_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target_item_path)

        except OSError:
            return False
        else:
            return True

    def _try_fetch_tag_variations(
        self, tag_variations: list[str], temp_clone_dir: Path
    ) -> bool:
        tag_checkout_and_copy_successful = False
        for tag in tag_variations:
            checkout_process = self._run_git_command(
                ["git", "-C", str(temp_clone_dir), "checkout", tag],
                check_errors=False,
            )
            if checkout_process and checkout_process.returncode == 0:
                logger.info(f"Checkout of tag '{tag}' successful in {temp_clone_dir}.")
                self._cleanup_target_dir_content()
                if not self._ensure_target_dir_exists():
                    break

                if self._copy_cloned_content(temp_clone_dir, self.download_target_path):
                    tag_checkout_and_copy_successful = True
                break
        return tag_checkout_and_copy_successful

    def _try_fetch_tag_full_clone_checkout(
        self, repo_url: str, tag_variations: list[str]
    ) -> bool:
        """Attempt to fetch a tag by doing a full clone then checking out the tag."""
        temp_clone_dir = (
            self.base_save_path
            / f"{self._sanitize_path_component(self.package_name)}_temp_dl"
            / "full_clone"
        )

        cloned_successfully = False

        try:
            if temp_clone_dir.exists():
                shutil.rmtree(temp_clone_dir)

            if not self._run_git_command(
                ["git", "clone", repo_url, str(temp_clone_dir)]
            ):
                return False
            cloned_successfully = True

            tag_checkout_and_copy_successful = self._try_fetch_tag_variations(
                tag_variations=tag_variations, temp_clone_dir=temp_clone_dir
            )

            return tag_checkout_and_copy_successful
        finally:
            if (cloned_successfully and temp_clone_dir.exists()) or (
                not cloned_successfully and temp_clone_dir.exists()
            ):
                shutil.rmtree(temp_clone_dir)

    def _fetch_from_vcs_tag(self, repo_url: str) -> bool:
        logger.info(
            f"Attempt to fetch the tag '{self.package_version}' "
            f"from VCS: {repo_url}"
        )
        tag_variations_set = {
            self.package_version,
            f"v{self.package_version}",
            f"refs/tags/{self.package_version}",
            f"refs/tags/v{self.package_version}",
            f"{self.package_name}-{self.package_version}",
            f"{self.package_name}/{self.package_version}",
            f"{self.package_name}/v{self.package_version}",
            f"release-{self.package_version}",
        }
        if self.package_version.startswith("v") and len(self.package_version) > 1:
            tag_variations_set.add(self.package_version[1:])

        tag_variations = [t for t in tag_variations_set if t]
        preferred_order = [self.package_version, f"v{self.package_version}"]
        ordered_tag_variations = preferred_order + [
            t for t in tag_variations if t not in preferred_order
        ]

        if self._try_fetch_tag_github_archive(repo_url, ordered_tag_variations):
            return True

        if self._try_fetch_tag_shallow_clone(repo_url, ordered_tag_variations):
            return True

        return self._try_fetch_tag_full_clone_checkout(repo_url, ordered_tag_variations)

    def _fetch_from_vcs_main(self, repo_url: str) -> bool:
        """Fetch the main/default branch from VCS into self.download_target_path."""
        logger.info(f"Attempt to fetch the main/default branch from VCS: {repo_url}")
        self._cleanup_target_dir_content()
        if not self._ensure_target_dir_exists():
            logger.error(
                "Unable to prepare target directory for the VCS main branch clone."
            )
            return False

        if self._run_git_command(
            ["git", "clone", "--depth", "1", repo_url, str(self.download_target_path)]
        ):
            self._cleanup_git_dir_from_path(self.download_target_path)
            logger.info(
                "branch main/default Clone "
                f"successful in {self.download_target_path}."
            )
            return True
        return False

    def fetch(self) -> tuple[bool, bool, str | None]:
        """Fetch repository.

        Returns:
            tuple[bool, bool, str | None]:
                - fetch_successful: True se il fetch succeed,
                    False otherwise.
                - is_master_branch_fetched: True if master/default branch fetched.
                - path_to_return: path to sources directory downloaded
                    if fetch is successful, None otherwise.

        """
        fetch_successful = False
        is_master_branch_fetched = False
        path_to_return: str | None = None

        logger.info(
            f"--- Starting fetch for {self.package_name} v{self.package_version} ---"
        )
        if self.download_target_path.exists() and any(
            self.download_target_path.iterdir()
        ):
            self._cleanup_git_dir_from_path(self.download_target_path)
            fetch_successful = True
            path_to_return = str(self.download_target_path)
        if not fetch_successful and self._fetch_from_pypi():
            fetch_successful = True
            path_to_return = str(self.download_target_path)

        if not fetch_successful:
            vcs_url = self._get_vcs_url()
            if vcs_url:
                if self._fetch_from_vcs_tag(vcs_url):
                    fetch_successful = True
                    path_to_return = str(self.download_target_path)
                elif self._fetch_from_vcs_main(vcs_url):
                    fetch_successful = True
                    is_master_branch_fetched = True
                    path_to_return = str(self.download_target_path)

        if not fetch_successful:
            self._cleanup_target_dir_content()

        return fetch_successful, is_master_branch_fetched, path_to_return


def _pprint_(data: dict | list) -> None:
    logger.info(json.dumps(data, sort_keys=True, indent=4))


def main() -> None:
    """Test purpose."""
    test_packages = [
        {
            "name": "requests",
            "version": "2.25.1",
            "project_urls": {"Source Code": "https://github.com/psf/requests"},
        },
        {"name": "non_existent_package", "version": "1.0.0"},
        {
            "name": "flask",
            "version": "2.0.1",
            "project_urls": {"Repository": "https://github.com/pallets/flask"},
        },
    ]

    for p_info in test_packages:
        logger.info(f"\n>>> Testing fetch for: {p_info['name']} v{p_info['version']}")
        fetcher_obj = PackageSourceFetcher(
            base_save_path="devildex_fetcher_test_output", package_info_dict=p_info
        )
        success, is_master, path_str = fetcher_obj.fetch()
        if success:
            logger.info(f"    SUCCESS: Path: {path_str}, Is Master: {is_master}")
        else:
            logger.error(f"    FAILED to fetch {p_info['name']}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    Path("devildex_fetcher_test_output").mkdir(exist_ok=True)
    main()
