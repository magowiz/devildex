import json
import logging
import pathlib
import re
import shutil
import subprocess
import tarfile
import zipfile

import requests

from devildex.local_data_parse.common_read import \
    get_explicit_dependencies_from_project_config
from devildex.local_data_parse.venv_inventory import \
    get_installed_packages_with_project_urls

logger = logging.getLogger(__name__)


class PackageSourceFetcher:
    def __init__(self, base_save_path: str, package_info_dict: dict):
        self.base_save_path = pathlib.Path(base_save_path)

        self.package_name = package_info_dict.get("name")
        self.package_version = package_info_dict.get("version")
        self.project_urls = package_info_dict.get("project_urls", {})

        if not self.package_name or not self.package_version:
            raise ValueError(
                "Nome del pacchetto e versione devono essere forniti in package_info_dict."
            )

        sane_pkg_name = self._sanitize_path_component(self.package_name)
        sane_pkg_version = self._sanitize_path_component(self.package_version)

        self.download_target_path = (
            self.base_save_path / sane_pkg_name / sane_pkg_version
        )

        self._determined_vcs_url = None
        logger.debug(
            f"Fetcher inizializzato per {self.package_name} v{self.package_version}. Target: {self.download_target_path}"
        )

    def _sanitize_path_component(self, name: str) -> str:
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
            if self.download_target_path.exists():
                if not any(self.download_target_path.iterdir()):
                    logger.info(
                        f"La directory di destinazione {self.download_target_path} esiste ed è vuota. Pronta per il download."
                    )
            else:
                self.download_target_path.mkdir(parents=True, exist_ok=True)
                logger.info(
                    f"Directory di destinazione creata: {self.download_target_path}"
                )
            return True
        except OSError as e:
            logger.error(
                f"Errore nella creazione o accesso alla directory di destinazione {self.download_target_path}: {e}"
            )
            return False

    def _cleanup_target_dir_content(self):
        if not self.download_target_path.exists():
            return
        logger.info(
            f"Pulizia del contenuto della directory di destinazione: {self.download_target_path}"
        )
        try:
            for item in self.download_target_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        except OSError as e:
            logger.error(
                f"Errore durante la pulizia della directory {self.download_target_path}: {e}"
            )

    def _get_vcs_url(self) -> str | None:
        if self._determined_vcs_url:  # Cache se già determinato
            return self._determined_vcs_url

        # Inizia con gli URL forniti (dai metadati locali)
        current_urls_to_check = self.project_urls
        source_of_urls = "locali"

        # Se gli URL locali sono vuoti o non contengono link ovvi, prova a prenderli da PyPI
        # Potremmo essere più specifici qui (es. se mancano "Source", "Source Code", ecc.)
        # Per ora, proviamo se current_urls_to_check è semplicemente vuoto.
        if not current_urls_to_check:
            logger.warning(
                f"I Project URLs per {self.package_name} v{self.package_version} sono vuoti localmente. Tentativo di fetch da PyPI JSON API."
            )
            try:
                api_url = f"https://pypi.org/pypi/{self.package_name}/{self.package_version}/json"
                response = requests.get(api_url, timeout=15)  # Timeout ragionevole
                response.raise_for_status()
                pypi_data = response.json()
                # L'API JSON di PyPI restituisce project_urls come dizionario sotto 'info'
                fetched_pypi_urls = pypi_data.get("info", {}).get("project_urls", {})
                if fetched_pypi_urls:
                    logger.info(
                        f"Recuperati con successo i project_urls da PyPI JSON API per {self.package_name}."
                    )
                    current_urls_to_check = (
                        fetched_pypi_urls  # Usa questi URL più freschi/completi
                    )
                    source_of_urls = "PyPI API"
                else:
                    logger.warning(
                        f"Nessun project_urls trovato nell'API JSON di PyPI per {self.package_name}."
                    )
            except requests.RequestException as e:
                logger.error(
                    f"Fallito il recupero dei project_urls da PyPI JSON API per {self.package_name}: {e}"
                )
            except ValueError:
                logger.error(
                    f"Fallita l'analisi JSON dei project_urls da PyPI per {self.package_name}"
                )

            if (
                not current_urls_to_check
            ):
                current_urls_to_check = {}

        preferred_labels = ["Source Code", "Source", "Repository"]
        for label in preferred_labels:
            url = current_urls_to_check.get(label)
            if url and self._is_valid_vcs_url(url):
                self._determined_vcs_url = url
                logger.info(f"URL VCS determinato ({label} da {source_of_urls}): {url}")
                return url

        homepage_url = current_urls_to_check.get("Homepage")
        if homepage_url and self._is_valid_vcs_url(homepage_url):
            self._determined_vcs_url = homepage_url
            logger.info(
                f"URL VCS determinato (Homepage da {source_of_urls}): {homepage_url}"
            )
            return homepage_url

        docs_url = current_urls_to_check.get("Documentation")
        if docs_url and "readthedocs.io" in docs_url:
            logger.info(
                f"Trovato URL ReadTheDocs ({docs_url} da {source_of_urls}). L'inferenza avanzata dell'URL VCS da RTD non è implementata in questa versione."
            )

        logger.warning(
            f"Nessun URL VCS valido trovato per {self.package_name} usando le fonti URL {source_of_urls}."
        )
        return None

    def _is_valid_vcs_url(self, url: str) -> bool:
        if not url:
            return False
        return any(
            host in url for host in ["github.com", "gitlab.com", "bitbucket.org"]
        ) or url.endswith(".git")

    def _download_and_extract_archive(
        self, url: str, temp_base_dir: pathlib.Path
    ) -> bool:
        archive_filename = temp_base_dir / url.split("/")[-1].split("?")[0]
        temp_extract_dir = temp_base_dir / "extracted_content"

        try:
            temp_base_dir.mkdir(parents=True, exist_ok=True)
            temp_extract_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Download dell'archivio da {url} a {archive_filename}")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            with open(archive_filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Archivio scaricato: {archive_filename}")

            logger.info(f"Estrazione di {archive_filename} in {temp_extract_dir}...")
            if str(archive_filename).lower().endswith(".zip"):
                with zipfile.ZipFile(archive_filename, "r") as zip_ref:
                    zip_ref.extractall(temp_extract_dir)
            elif (
                str(archive_filename)
                .lower()
                .endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar"))
            ):
                with tarfile.open(archive_filename, "r:*") as tar_ref:
                    tar_ref.extractall(temp_extract_dir)
            else:
                logger.error(f"Tipo di archivio non supportato: {archive_filename}")
                return False

            logger.info(
                f"Archivio estratto in {temp_extract_dir}. Spostamento del contenuto..."
            )

            extracted_items = list(temp_extract_dir.iterdir())
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                content_source_dir = extracted_items[0]
                logger.info(
                    f"Archivio contiene una singola directory radice: {content_source_dir.name}"
                )
            else:
                content_source_dir = temp_extract_dir
                logger.info(
                    f"Archivio contiene elementi multipli o nessun wrapper directory. Uso: {content_source_dir.name}"
                )

            for item in content_source_dir.iterdir():
                destination_item = self.download_target_path / item.name
                if item.is_dir():
                    if destination_item.exists():
                        shutil.rmtree(destination_item)
                    shutil.move(str(item), str(destination_item))
                else:
                    shutil.move(str(item), str(destination_item))

            logger.info(
                f"Contenuto spostato con successo in {self.download_target_path}"
            )
            return True

        except requests.RequestException as e:
            logger.error(f"Errore nel download di {url}: {e}")
        except (zipfile.BadZipFile, tarfile.TarError, tarfile.ReadError) as e:
            logger.error(f"Errore nell'estrazione di {archive_filename}: {e}")
        except Exception as e:
            logger.error(f"Errore generico durante download/estrazione di {url}: {e}")
        finally:
            if temp_base_dir.exists():
                shutil.rmtree(temp_base_dir)
        return False

    def _run_git_command(
        self, command_list: list, cwd: pathlib.Path | None = None, check_errors=True
    ) -> subprocess.CompletedProcess | None:
        cmd_str = " ".join(command_list)
        logger.info(
            f"Esecuzione comando git: {cmd_str} {'in ' + str(cwd) if cwd else ''}"
        )
        try:
            process = subprocess.run(
                command_list,
                capture_output=True,
                text=True,
                check=check_errors,
                cwd=cwd,
                encoding="utf-8",
                errors="replace",
            )
            if process.stdout:
                logger.debug(f"Git stdout:\n{process.stdout.strip()}")
            if process.stderr:
                logger.debug(f"Git stderr:\n{process.stderr.strip()}")
            return process
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Comando git fallito: {cmd_str}\nStdout: {e.stdout}\nStderr: {e.stderr}"
            )
        except FileNotFoundError:
            logger.error(
                "Comando git non trovato. Git è installato e nel PATH di sistema?"
            )
        except Exception as e:
            logger.error(
                f"Errore imprevisto durante l'esecuzione di git: {cmd_str}\n{e}"
            )
        return None

    def _cleanup_git_dir_from_path(self, path_to_clean: pathlib.Path) -> bool:
        git_dir = path_to_clean / ".git"
        if git_dir.is_dir():
            logger.info(f"Rimozione della directory .git da {path_to_clean}")
            try:
                shutil.rmtree(git_dir)
                return True
            except OSError as e:
                logger.error(f"Errore nella rimozione della directory .git: {e}")
                return False
        return True

    def _fetch_from_pypi(self) -> bool:
        logger.info(
            f"Tentativo di fetch da PyPI per {self.package_name} v{self.package_version}..."
        )
        api_url = (
            f"https://pypi.org/pypi/{self.package_name}/{self.package_version}/json"
        )
        try:
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            sdist_url = next(
                (
                    f["url"]
                    for f in data.get("urls", [])
                    if f.get("packagetype") == "sdist"
                ),
                None,
            )

            if not sdist_url:
                logger.warning(
                    f"Nessun sdist trovato su PyPI per {self.package_name} v{self.package_version}."
                )
                return False

            logger.info(f"Trovato URL sdist: {sdist_url}")
            temp_dir_for_pypi = (
                self.base_save_path
                / f"{self._sanitize_path_component(self.package_name)}_pypi_temp"
            )
            if self._download_and_extract_archive(sdist_url, temp_dir_for_pypi):
                logger.info(
                    f"Fetch e estrazione da PyPI riusciti per {self.package_name} v{self.package_version}."
                )
                return True
        except requests.RequestException as e:
            logger.error(f"Richiesta API PyPI fallita per {self.package_name}: {e}")
        except ValueError as e:
            logger.error(
                f"Errore nel parsing della risposta JSON da PyPI per {self.package_name}: {e}"
            )
        return False

    def _fetch_from_vcs_tag(self, repo_url: str) -> bool:
        logger.info(
            f"Tentativo di fetch del tag '{self.package_version}' da VCS: {repo_url}"
        )
        tag_variations = list(
            dict.fromkeys(
                [
                    self.package_version,
                    f"v{self.package_version}",
                    f"refs/tags/{self.package_version}",
                    f"refs/tags/v{self.package_version}",
                    f"{self.package_name}-{self.package_version}",
                    f"{self.package_name}/{self.package_version}",
                    f"{self.package_name}/v{self.package_version}",
                    f"release-{self.package_version}",
                    (
                        self.package_version[1:]
                        if self.package_version.startswith("v")
                        else None
                    ),
                ]
            )
        )
        tag_variations = [t for t in tag_variations if t]

        if "github.com" in repo_url:
            repo_path = repo_url.split("github.com/")[-1].replace(".git", "")
            for tag in tag_variations:
                candidate_tag_name_for_url = tag.replace("refs/tags/", "")
                urls_to_try = [
                    f"https://github.com/{repo_path}/archive/refs/tags/{candidate_tag_name_for_url}.tar.gz",
                    f"https://github.com/{repo_path}/archive/refs/tags/{candidate_tag_name_for_url}.zip",
                    f"https://github.com/{repo_path}/archive/{candidate_tag_name_for_url}.tar.gz",
                    f"https://github.com/{repo_path}/archive/{candidate_tag_name_for_url}.zip",
                ]
                for archive_url in urls_to_try:
                    logger.info(
                        f"Tentativo download diretto archivio tag '{candidate_tag_name_for_url}': {archive_url}"
                    )
                    temp_dir_for_archive = (
                        self.base_save_path
                        / f"{self._sanitize_path_component(self.package_name)}_archive_temp"
                    )
                    if self._download_and_extract_archive(
                        archive_url, temp_dir_for_archive
                    ):
                        logger.info(
                            f"Fetch e estrazione del tag '{candidate_tag_name_for_url}' da archivio VCS riusciti."
                        )
                        return True

        logger.info(
            "Download diretto archivio fallito o URL non GitHub. Tentativo con 'git clone --depth 1 --branch <tag>'."
        )
        for tag in tag_variations:
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
                    f"Clone del tag '{tag}' riuscito in {self.download_target_path}."
                )
                return True

        logger.info(
            "Clone con '--depth 1 --branch <tag>' fallito. Tentativo con clone completo e checkout."
        )
        temp_clone_dir = (
            self.base_save_path
            / f"{self._sanitize_path_component(self.package_name)}_full_clone_temp"
        )
        if temp_clone_dir.exists():
            shutil.rmtree(temp_clone_dir)

        if self._run_git_command(["git", "clone", repo_url, str(temp_clone_dir)]):
            success = False
            for tag in tag_variations:
                checkout_process = self._run_git_command(
                    ["git", "-C", str(temp_clone_dir), "checkout", tag],
                    check_errors=False,
                )
                if checkout_process and checkout_process.returncode == 0:
                    logger.info(
                        f"Checkout del tag '{tag}' riuscito in {temp_clone_dir}."
                    )
                    for item in temp_clone_dir.iterdir():
                        if item.name == ".git":
                            continue
                        destination_item = self.download_target_path / item.name
                        if item.is_dir():
                            if destination_item.exists():
                                shutil.rmtree(destination_item)
                            shutil.copytree(item, destination_item)
                        else:
                            shutil.copy2(item, destination_item)
                    success = True
                    break
            shutil.rmtree(temp_clone_dir)
            if success:
                logger.info(
                    f"Contenuto del tag copiato con successo in {self.download_target_path}."
                )
                return True
        else:
            if temp_clone_dir.exists():
                shutil.rmtree(temp_clone_dir)

        logger.warning(
            f"Impossibile trovare o fare checkout di un tag corrispondente alla versione {self.package_version} in {repo_url}."
        )
        return False

    def _fetch_from_vcs_main(self, repo_url: str) -> bool:
        logger.info(
            f"Tentativo di fetch del branch principale/default da VCS: {repo_url}"
        )
        if self._run_git_command(
            ["git", "clone", "--depth", "1", repo_url, str(self.download_target_path)]
        ):
            self._cleanup_git_dir_from_path(self.download_target_path)
            logger.info(
                f"Clone del branch principale/default riuscito in {self.download_target_path}."
            )
            return True
        logger.error(
            f"Fallimento nel clonare il branch principale/default da {repo_url}."
        )
        return False

    def fetch(self) -> tuple[bool, bool, str | None]:
        master = False
        logger.info(
            f"--- Inizio fetch per {self.package_name} v{self.package_version} ---"
        )

        if self.download_target_path.exists() and any(
            self.download_target_path.iterdir()
        ):
            logger.info(
                f"La directory {self.download_target_path} esiste e non è vuota. Si presume già scaricata."
            )
            self._cleanup_git_dir_from_path(self.download_target_path)
            return True, master, str(self.download_target_path)

        if self.download_target_path.exists():
            self._cleanup_target_dir_content()

        if not self._ensure_target_dir_exists():
            logger.error("Impossibile preparare la directory di destinazione.")
            return False, False, None

        if self._fetch_from_pypi():
            logger.info(
                f"Fetch da PyPI riuscito per {self.package_name} v{self.package_version}."
            )
            return True, master, str(self.download_target_path)
        logger.info("Fetch da PyPI fallito o sdist non trovato. Tentativo con VCS.")

        vcs_url = self._get_vcs_url()
        if not vcs_url:
            logger.warning(
                f"Nessun URL VCS trovato per {self.package_name}. Impossibile tentare fetch da VCS."
            )
            logger.info(
                f"--- Fetch FALLITO per {self.package_name} v{self.package_version} ---"
            )
            return False, False, None

        if self._fetch_from_vcs_tag(vcs_url):
            logger.info(
                f"Fetch da VCS (tag) riuscito per {self.package_name} v{self.package_version}."
            )
            return True, master, str(self.download_target_path)
        logger.info("Fetch da VCS (tag) fallito. Tentativo con branch principale VCS.")
        master = True

        logger.warning(
            f"Fallback: tentativo di fetch del branch principale/default per {self.package_name} da {vcs_url}"
        )
        if self._fetch_from_vcs_main(vcs_url):
            logger.info(
                f"Fetch da VCS (branch principale) riuscito per {self.package_name} v{self.package_version}."
            )
            return True, master, str(self.download_target_path)

        logger.error(
            f"Tutti i tentativi di fetch sono falliti per {self.package_name} v{self.package_version}."
        )
        logger.info(
            f"--- Fetch FALLITO per {self.package_name} v{self.package_version} ---"
        )
        self._cleanup_target_dir_content()
        return False, False, None


def _pprint_(data):
    print(json.dumps(data, sort_keys=True, indent=4))


def main():
    explicit = get_explicit_dependencies_from_project_config()
    pkg_info = get_installed_packages_with_project_urls(explicit=explicit)
    _pprint_(pkg_info)
    for p_info in pkg_info:
        pf_obj = PackageSourceFetcher("suca", p_info)
        result = pf_obj.fetch()
        if result[0]:
            resp = result[2]
            if result[1]:
                resp = "MASTER : " + resp
            print(resp)
        else:
            print("failed")


if __name__ == "__main__":
    main()
