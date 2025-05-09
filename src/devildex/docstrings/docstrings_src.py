"""docstrings pdoc3 module."""

import importlib
import os
import re
import shutil
import subprocess
import sys
import traceback
import venv
from pathlib import Path
from types import ModuleType

import pdoc

CONFIG_FILE = "../../../devildex_config.ini"


class DocStringsSrc:
    def __init__(self):
        """Initialize il DocStringsSrc."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.docset_dir = project_root / "docset"
        self.docset_dir.mkdir(parents=True, exist_ok=True)

    def _try_process_module(
        self,
        module_name_to_process: str,
        context: pdoc.Context,
        venv_python_interpreter: str | None,
    ) -> list[pdoc.Module]:
        processed_pdoc_modules: list[pdoc.Module] = []
        module_obj: ModuleType | None = None
        pdoc_module_instance: pdoc.Module | None = None

        for attempt in range(2):
            try:
                current_module_obj_candidate = pdoc.import_module(
                    module_name_to_process, reload=True, skip_errors=True
                )

                is_dummy = (
                    not hasattr(current_module_obj_candidate, "__file__")
                    and not hasattr(current_module_obj_candidate, "__path__")
                    and (
                        not hasattr(current_module_obj_candidate, "__name__")
                        or current_module_obj_candidate.__name__
                        != module_name_to_process
                    )
                )

                if is_dummy:
                    if attempt == 0 and venv_python_interpreter:
                        raise ModuleNotFoundError(
                            f"No module named '{module_name_to_process}' "
                            "(pdoc returned dummy object)"
                        )
                    else:
                        module_obj = None
                        break

                module_obj = current_module_obj_candidate
                pdoc_module_instance = pdoc.Module(module_obj, context=context)
                break

            except (ModuleNotFoundError, ImportError) as import_err:
                module_obj = None
                pdoc_module_instance = None
                if attempt == 0 and venv_python_interpreter:
                    missing_module_name = self._extract_missing_module_name(
                        str(import_err)
                    )
                    if (
                        missing_module_name
                        and missing_module_name.strip()
                        and missing_module_name != module_name_to_process
                    ):
                        try:
                            pip_install_cmd = [
                                str(venv_python_interpreter),
                                "-m",
                                "pip",
                                "install",
                                missing_module_name,
                            ]
                            install_result = subprocess.run(
                                pip_install_cmd,
                                check=False,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                            )
                            if install_result.returncode == 0:
                                print(
                                    f"Installazione di '{missing_module_name}' "
                                    f"completata. "
                                    f"Riprovo l'importazione di "
                                    f"'{module_name_to_process}'."
                                )
                                if missing_module_name in sys.modules:
                                    del sys.modules[missing_module_name]
                                importlib.invalidate_caches()
                            else:
                                print(
                                    "ERRORE: Fallita installazione di "
                                    f"'{missing_module_name}':"
                                )
                                print(f"  Stdout: {install_result.stdout.strip()}")
                                print(f"  Stderr: {install_result.stderr.strip()}")
                                break
                        except Exception as pip_exec_err:
                            print(
                                "ERRORE: Eccezione durante il tentativo di installare "
                                f"'{missing_module_name}': {pip_exec_err}"
                            )
                            break
                    else:
                        break
                else:
                    break
            except Exception:
                pdoc_module_instance = None
                break

        if pdoc_module_instance and module_obj:
            processed_pdoc_modules.append(pdoc_module_instance)
            print(
                f"INFO: Modulo principale '{module_name_to_process}' "
                "wrappato con successo."
            )
        elif (
            module_obj
            and isinstance(module_obj, ModuleType)
            and hasattr(module_obj, "__path__")
        ):
            print(
                f"INFO: Modulo principale '{module_name_to_process}' non wrappato. "
                "Tentativo recupero sottomoduli..."
            )
            found_salvageable_submodule = False
            for submodule_info in pdoc.iter_submodules(module_obj):
                submodule_qualname = submodule_info.name
                try:
                    submodule_actual_obj = pdoc.import_module(
                        submodule_qualname, reload=True, skip_errors=False
                    )
                    if not submodule_actual_obj:
                        continue
                    sub_pdoc_instance = pdoc.Module(
                        submodule_actual_obj, context=context
                    )
                    processed_pdoc_modules.append(sub_pdoc_instance)
                    print(
                        "  SUCCESS: Recuperato e wrappato sottomodulo "
                        f"'{submodule_qualname}'."
                    )
                    found_salvageable_submodule = True
                except ImportError as sub_import_err:
                    print(
                        "  FAILED IMPORT (sottomodulo): Impossibile importare "
                        f"'{submodule_qualname}': {sub_import_err}"
                    )
                except Exception as sub_wrap_err:
                    print(
                        "  FAILED WRAP (sottomodulo): Errore durante il wrapping di "
                        f"'{submodule_qualname}': {sub_wrap_err.__class__.__name__}: "
                        f"{sub_wrap_err}"
                    )
            if not found_salvageable_submodule:
                print(
                    f"INFO: Nessun sottomodulo di '{module_name_to_process}' "
                    "recuperato con successo."
                )
        elif module_obj:
            print(
                f"INFO: Modulo '{module_name_to_process}' importato ma non wrappato e "
                f"non è un package. Nessun sottomodulo da recuperare."
            )
        else:
            print(
                f"INFO: Modulo '{module_name_to_process}' non importato. "
                "Nessun sottomodulo da recuperare."
            )
        return processed_pdoc_modules

    def get_docset_dir(self):
        return self.docset_dir

    def _discover_modules_in_folder(self, input_folder_path: Path) -> list[str]:
        """Scopre i moduli e pacchetti Python di primo livello in una data cartella."""
        discovered_names = []
        for item_name in os.listdir(input_folder_path):
            item_path = input_folder_path / item_name
            if item_name.startswith((".", "__")):
                continue

            if item_path.is_file() and item_name.endswith(".py"):
                module_name = item_name[:-3]
                if module_name == "__init__":
                    continue
                discovered_names.append(module_name)
            elif item_path.is_dir():
                if (item_path / "__init__.py").exists():
                    package_name = item_name
                    discovered_names.append(package_name)
        return discovered_names

    def generate_docs_from_folder(
        self,
        input_folder: str,
        output_folder: str,
        modules_to_document: list[str] | None = None,
        venv_python_interpreter=None,
    ) -> bool:
        """Generate HTML documentation Python modules and saves them in output_folder.

        Adatta l'importazione a versioni di pdoc.import_module
        che non supportano l'argomento 'path' usando sys.path.

        Args:
            input_folder: path della cartella base contenente i moduli/pacchetti.
                          Questa cartella verrà temporaneamente aggiunta a sys.path.
            output_folder: Il percorso della cartella dove salvare l'HTML generato.
            modules_to_document: Una lista di nomi di moduli/pacchetti
                                 (es. ['my_module', 'my_package']). Se None, la funzione
                                 tenterà di scoprire i modules di alto livello in
                                 input_folder.

        Returns:
            True se la documentazione è stata generata con successo per
                almeno un modulo, False altrimenti (es. cartella non
                trovata, nessun modulo trovato,
                importazione fallita per tutti).
        """
        if not os.path.isdir(input_folder):
            print(f"Errore: La folder di input '{input_folder}' non esiste.")
            return False

        os.makedirs(output_folder, exist_ok=True)

        context = pdoc.Context()
        wrapped_modules: list[pdoc.Module] = []
        names_to_import: list[str] = []
        input_path_obj = Path(input_folder)

        if modules_to_document is not None:
            print(
                f"Utilizzo moduli specificati: {modules_to_document} dalla "
                f"cartella: {input_folder}"
            )
            names_to_import = modules_to_document
        else:
            print(f"Scansione della cartella per scoprire moduli: {input_folder}")
            names_to_import = self._discover_modules_in_folder(input_path_obj)

        if not names_to_import:
            print(
                "Nessun modulo o package Python trovato/specificato in "
                f"'{input_folder}'. "
                "Nessuna documentation generata."
            )
            return False

        original_sys_path = list(sys.path)
        sys.path.insert(0, input_folder)
        files_generated_count = 0
        try:
            for name in names_to_import:
                pdoc_instances_for_name = self._try_process_module(
                    name, context, venv_python_interpreter
                )
                if pdoc_instances_for_name:
                    wrapped_modules.extend(pdoc_instances_for_name)
                # --- FINE MODIFICA ---

            def recursive_htmls(mod: pdoc.Module):
                """Ricorsivamente genera l'HTML per un modulo e i suoi sottomoduli."""
                yield mod
                for submod in mod.submodules():
                    yield from recursive_htmls(submod)

            print(f"Generating HTML nella folder: {output_folder}")
            for root_module_obj in wrapped_modules:
                for current_pdoc_module in recursive_htmls(root_module_obj):
                    try:
                        html_content = current_pdoc_module.html()
                        if not html_content.strip():
                            print(
                                f"  WARNING: Contenuto HTML vuoto generato per "
                                f"{current_pdoc_module.qualname}. Saltato."
                            )
                            continue

                        relative_url_path = current_pdoc_module.url()
                        if relative_url_path.startswith("/"):
                            relative_url_path = relative_url_path[1:]

                        output_path_obj = Path(output_folder)
                        full_output_file_path = output_path_obj / Path(
                            relative_url_path
                        )

                        full_output_file_path.parent.mkdir(parents=True, exist_ok=True)

                        with open(full_output_file_path, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        files_generated_count += 1
                        print(
                            f"Saved: {full_output_file_path} "
                            f"(Module: {current_pdoc_module.qualname}, "
                            f"URL from pdoc: {relative_url_path})"
                        )
                    except Exception as html_gen_err:
                        print(
                            "  ERROR: Errore durante la generazione HTML o il "
                            f"salvataggio per {current_pdoc_module.qualname}: "
                            f"{html_gen_err}"
                        )

            if not wrapped_modules:
                print("Nessun modulo è stato importato e wrappato correttamente.")
                return False

            if files_generated_count > 0:
                print(
                    f"Generazione documentazione completata. {files_generated_count} "
                    f"file HTML salvati in {output_folder}."
                )
                return True

            else:
                print(
                    "ATTENZIONE: Nessun file HTML è stato generato in"
                    f" {output_folder}, "
                    "sebbene alcuni moduli fossero stati wrappati."
                )
                return False

        finally:
            sys.path = original_sys_path

    def cleanup_folder(self, folder_or_list: Path | str | list[Path | str]):
        """Pulisce una singola cartella/file o una lista di cartelle/file.
        Gestisce sia stringhe che oggetti pathlib.Path.
        """
        items_to_clean = []
        if isinstance(folder_or_list, list):
            items_to_clean.extend(folder_or_list)
        else:
            items_to_clean.append(folder_or_list)

        for item in items_to_clean:
            item_path = Path(item)
            if not item_path.exists():
                continue

            if item_path.is_dir():
                shutil.rmtree(item_path, ignore_errors=True)
            elif item_path.is_file():
                try:
                    item_path.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass

    def git_clone(self, repo_url, clone_dir_path, default_branch="master"):
        """Clone a git repository."""
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    default_branch,
                    repo_url,
                    clone_dir_path,
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except Exception:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    "main",
                    repo_url,
                    clone_dir_path,
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

    def _extract_missing_module_name(self, error_message: str) -> str | None:
        """Estrae il nome del modulo da un messaggio di ModuleNotFoundError.

        Es. "No module named 'X'" -> "X"
        """
        match = re.search(r"No module named '([^']*)'", error_message)
        if match:
            return match.group(1)
        return None

    def run(self, url, project_name, version=""):
        """Run logic."""
        cloned_repo_path: Path | None = None
        temp_venv_path: Path | None = None
        try:
            cloned_repo_path = Path(project_name)
            temp_venv_path = cloned_repo_path / ".venv_docs"

            final_output_dir = self.docset_dir / project_name / version
            tmp_output_dir = self.docset_dir / f"tmp_{project_name}" / version

            self.cleanup_folder(
                [cloned_repo_path, temp_venv_path, final_output_dir, tmp_output_dir]
            )

            self.git_clone(url, cloned_repo_path)

            venv.create(temp_venv_path, with_pip=True, clear=True)

            if sys.platform == "win32":
                _venv_python_rel = temp_venv_path / "Scripts" / "python.exe"
            else:
                _venv_python_rel = temp_venv_path / "bin" / "python"
            venv_python_interpreter = str(_venv_python_rel.resolve())

            get_site_packages_command = [
                venv_python_interpreter,
                "-c",
                "import site; print(site.getsitepackages()[0])",
            ]
            result = subprocess.run(
                get_site_packages_command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            venv_site_packages = result.stdout.strip()
            subprocess.run(
                [venv_python_interpreter, "-m", "pip", "install", "."],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=cloned_repo_path,
            )

            subprocess.run(
                [venv_python_interpreter, "-m", "pip", "install", "pdoc3"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            original_sys_path_inner = list(sys.path)

            sys.path.insert(0, venv_site_packages)
            print(f"Added {venv_site_packages} a sys.path")
            try:
                print("Esecuzione generate_docs_from_folder con venv sys.path...")
                success = self.generate_docs_from_folder(
                    str(cloned_repo_path),
                    str(tmp_output_dir),
                    modules_to_document=[project_name],
                    venv_python_interpreter=venv_python_interpreter,
                )

                if success:
                    print(
                        "Generazione documentazione completata con successo per"
                        f" {project_name}"
                    )
                    if final_output_dir.exists():
                        self.cleanup_folder(final_output_dir)
                    shutil.move(tmp_output_dir, final_output_dir)
                else:
                    print(
                        "Generazione documentazione failed o nessun modulo documentato "
                        f"per {project_name}"
                    )

            finally:
                sys.path = original_sys_path_inner
                print(f"Removed {venv_site_packages} da sys.path")
                if tmp_output_dir.exists():
                    self.cleanup_folder(tmp_output_dir)
        except subprocess.CalledProcessError as cpe:
            print(f"\nERROR durante l'esecuzione di un comando pip: {cpe.cmd}")
            print(f"Codice di uscita: {cpe.returncode}")
            print(f"Output del comando (stdout):\n---\n{cpe.stdout}\n---")
            print(f"Errors del comando (stderr):\n---\n{cpe.stderr}\n---")
        except RuntimeError as e:
            print(f"\nERROR durante la fase di preparazione (es. clonazione): {e}")
        except Exception as e:
            print(f"\nUnexpected ERROR durante il process di {project_name}: {e}")
            print("--- TRACEBACK ---")
            traceback.print_exc()
            print("--- FINE DETTAGLIO ERROR IMPREVISTO ---")
        finally:
            print(f"Pulizia delle temporary folders per {project_name}...")
            if cloned_repo_path:
                self.cleanup_folder(cloned_repo_path)
            if temp_venv_path:
                self.cleanup_folder(temp_venv_path)
            print(f"Pulizia delle temporanee folders per {project_name} completed.")


if __name__ == "__main__":
    P_URL = "https://github.com/psf/black"
    p_name = P_URL.rsplit("/", maxsplit=1)[-1]
    d_src = DocStringsSrc()
    d_src.run(P_URL, p_name)
