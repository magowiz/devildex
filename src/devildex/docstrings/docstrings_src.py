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
        """
        Inizializza il DocStringsSrc.

        Args:
            base_output_path: Il percorso base dove verrà creata la documentazione finale
                              (es. 'PROJECT_ROOT/docset').
        """
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.docset_dir = project_root / "docset"
        self.docset_dir.mkdir(parents=True, exist_ok=True)

    def get_docset_dir(self):
        return self.docset_dir


    def generate_docs_from_folder(
            self, input_folder: str, output_folder: str, modules_to_document: list[str] | None = None,
            venv_python_interpreter=None
        ) -> bool:
            """Genera la documentazione HTML per i moduli Python specificati o trovati in input_folder
            e li salva in output_folder. Adatta l'importazione a versioni di pdoc.import_module
            che non supportano l'argomento 'path' usando sys.path.

            Args:
                input_folder: Il percorso della cartella base contenente i moduli/pacchetti.
                              Questa cartella verrà temporaneamente aggiunta a sys.path.
                output_folder: Il percorso della cartella dove salvare l'HTML generato.
                modules_to_document: Una lista di nomi di moduli/pacchetti
                                     (es. ['my_module', 'my_package']). Se None, la funzione
                                     tenterà di scoprire i moduli di alto livello in input_folder.

            Returns:
                True se la documentazione è stata generata con successo per almeno un modulo,
                False altrimenti (es. cartella non trovata, nessun modulo trovato,
                    importazione fallita per tutti).
            """
            if not os.path.isdir(input_folder):
                print(f"Errore: La folder di input '{input_folder}' non esiste.")
                return False

            os.makedirs(output_folder, exist_ok=True)

            context = pdoc.Context()
            wrapped_modules: list[pdoc.Module] = []
            names_to_import: list[str] = []

            if modules_to_document is not None:
                print(
                    f"Utilizzo moduli specificati: {modules_to_document} dalla cartella: {input_folder}"
                )
                names_to_import = modules_to_document
            else:
                print(f"Scansione della cartella per scoprire moduli: {input_folder}")
                for item_name in os.listdir(input_folder):
                    item_path = os.path.join(input_folder, item_name)
                    if item_name.startswith(".") or item_name.startswith("__"):
                        continue

                    if os.path.isfile(item_path) and item_name.endswith(".py"):
                        module_name = item_name[:-3]
                        if module_name == "__init__":
                            continue
                        print(f"Trovato modulo: {module_name}")
                        names_to_import.append(module_name)

                    elif os.path.isdir(item_path):
                        if os.path.exists(os.path.join(item_path, "__init__.py")):
                            package_name = item_name
                            print(f"Trovato package: {package_name}")
                            names_to_import.append(package_name)

            if not names_to_import:
                print(
                    f"Nessun modulo o package Python trovato/specificato in '{input_folder}'. "
                    "Nessuna documentation generata."
                )
                return False

            original_sys_path = list(sys.path)
            sys.path.insert(0, input_folder)

            try:
                for name in names_to_import:
                    module_obj = None
                    pdoc_module_instance = None

                    # Tentiamo l'importazione fino a 2 volte per permettere l'installazione dinamica
                    for attempt in range(2):  # Ciclo per 2 tentativi (0 e 1)
                        try:
                            # print(f"DEBUG: Tentativo {attempt + 1}/2 di importare e wrappare il modulo: '{name}'")
                            # Al primo tentativo, usiamo skip_errors=True.
                            # Al secondo tentativo (dopo un'eventuale installazione), potremmo usare skip_errors=False
                            # ma per ora manteniamo True per coerenza e per catturare altri errori di pdoc.
                            use_skip_errors = True  # Manteniamo True per ora

                            module_obj_candidate = pdoc.import_module(
                                name, reload=True, skip_errors=use_skip_errors
                            )

                            # Se skip_errors=True e otteniamo un dummy, e abbiamo un interprete venv,
                            # forziamo un errore per attivare la logica di recupero.
                            if use_skip_errors and (
                                    not hasattr(module_obj_candidate, "__file__") and not hasattr(module_obj_candidate,
                                                                                                  "__name__")):
                                if attempt == 0 and venv_python_interpreter:
                                    # Simula un ModuleNotFoundError per attivare il recupero
                                    # Questo aiuta se pdoc.import_module(skip_errors=True) maschera l'errore originale
                                    raise ModuleNotFoundError(
                                        f"No module named '{name}' (dedotto da import dummy con pdoc)")
                                else:
                                    # Se è il secondo tentativo o non c'è interprete, logga e salta
                                    print(
                                        f"WARNING: L'importazione di '{name}' è failed "
                                        "(import_module con skip_errors=True "
                                        "ha returned un dummy). Saltato."
                                    )
                                    module_obj = None  # Assicura che non venga processato
                                    break  # Esci dal ciclo dei tentativi per questo modulo

                            module_obj = module_obj_candidate
                            pdoc_module_instance = pdoc.Module(module_obj, context=context)
                            print(f"Importato e wrapped: {name}")
                            break  # Successo, esci dal ciclo dei tentativi (for attempt...)

                        except (ModuleNotFoundError, ImportError) as import_err:
                            if attempt == 0 and venv_python_interpreter:  # Solo al primo tentativo e se abbiamo come installare
                                missing_module_name = self._extract_missing_module_name(str(import_err))

                                # Evita di installare il modulo che stiamo cercando di documentare
                                # o se non riusciamo a estrarre un nome di modulo valido.
                                if missing_module_name and missing_module_name.strip() and missing_module_name != name:
                                    print(
                                        f"WARNING: Importazione di '{name}' fallita. Modulo dipendente mancante: '{missing_module_name}'.")
                                    print(
                                        f"Tentativo di installare '{missing_module_name}' nel venv: {venv_python_interpreter}")
                                    try:
                                        pip_install_cmd = [str(venv_python_interpreter), "-m", "pip", "install",
                                                           missing_module_name]
                                        install_result = subprocess.run(
                                            pip_install_cmd,
                                            check=False, capture_output=True, text=True, encoding="utf-8"
                                        )
                                        if install_result.returncode == 0:
                                            print(
                                                f"Installazione di '{missing_module_name}' completata. Riprovo l'importazione di '{name}'.")
                                            # Invalida le cache di importazione per forzare un nuovo import
                                            if missing_module_name in sys.modules:
                                                del sys.modules[missing_module_name]
                                            importlib.invalidate_caches()  # Richiede import importlib
                                            # Continua con il prossimo tentativo (attempt = 1)
                                        else:
                                            print(f"ERRORE: Fallita installazione di '{missing_module_name}':")
                                            print(f"  Stdout: {install_result.stdout.strip()}")
                                            print(f"  Stderr: {install_result.stderr.strip()}")
                                            module_obj = None  # Assicura che non venga processato
                                            break  # Fallita installazione, esci dal ciclo dei tentativi per questo modulo
                                    except Exception as pip_exec_err:
                                        print(
                                            f"ERRORE: Eccezione durante il tentativo di installare '{missing_module_name}': {pip_exec_err}")
                                        module_obj = None
                                        break  # Fallita installazione, esci dal ciclo dei tentativi
                                else:  # Nessun nome modulo dipendente estratto, o è il modulo stesso
                                    if attempt == 1:  # Se è il secondo tentativo, logga il fallimento finale
                                        print(
                                            f"WARNING: Fallito import/wrap di '{name}' (errore: {import_err}) anche dopo tentativo di recupero o perché il modulo mancante è '{name}' stesso.")
                                    else:  # Primo tentativo, ma non si tenta l'installazione
                                        print(
                                            f"WARNING: Errore di importazione per '{name}': {import_err}. Non si tenta l'installazione (modulo mancante non identificato come dipendenza o è '{name}' stesso).")
                                    module_obj = None
                                    break  # Esci dal ciclo dei tentativi
                            else:  # Secondo tentativo fallito o venv_python_interpreter non fornito
                                print(
                                    f"WARNING: {'Fallito ultimo tentativo di importare' if attempt == 1 else 'Errore durante limportazione di'} '{name}': {import_err}")
                                module_obj = None
                                break  # Esci dal ciclo dei tentativi

                        except Exception as e_other:  # Altre eccezioni (es. da pdoc.Module())
                            print(
                                f"WARNING: Errore imprevisto (non di importazione) durante il wrapping di '{name}' al tentativo {attempt + 1}: {e_other}")
                            module_obj = None
                            break  # Esci dal ciclo dei tentativi

                    # Fine del ciclo 'for attempt'
                    if pdoc_module_instance and module_obj:  # Assicurati che module_obj non sia None
                        wrapped_modules.append(pdoc_module_instance)
                    else:
                        print(f"INFO: Non è stato possibile wrappare il modulo '{name}' dopo tutti i tentativi.")
                def recursive_htmls(mod: pdoc.Module):
                    """Ricorsivamente genera l'HTML per un modulo e i suoi sottomoduli."""
                    yield mod
                    for submod in mod.submodules():
                        yield from recursive_htmls(submod)

                print(f"Generating HTML nella folder: {output_folder}")
                for root_module_obj in wrapped_modules:
                    for current_pdoc_module in recursive_htmls(root_module_obj):
                        html_content = current_pdoc_module.html()
                        relative_url_path = current_pdoc_module.url()
                        if relative_url_path.startswith("/"):
                            relative_url_path = relative_url_path[1:]

                        full_output_path = os.path.join(output_folder, relative_url_path)

                        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)

                        try:
                            with open(full_output_path, "w", encoding="utf-8") as f:
                                f.write(html_content)
                            print(
                                f"Saved: {full_output_path} (Module: {current_pdoc_module.qualname}, "
                                f"URL from pdoc: {relative_url_path})"
                            )
                        except IOError as e:
                            print(f"Error during il salvataggio di {full_output_path}: {e}")

                print("Generazione documentation completed.")
                return True

            finally:
                sys.path = original_sys_path


    def cleanup_folder(self, folder):
        if isinstance(folder, list):
            for f in folder:
                self.cleanup_folder(f)
            return

        if os.path.isdir(folder):
            shutil.rmtree(folder)


    def git_clone(self, repo_url, clone_dir_path, default_branch="master"):
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
        """
        Estrae il nome del modulo da un messaggio di ModuleNotFoundError.
        Es. "No module named 'X'" -> "X"
        """
        match = re.search(r"No module named '([^']*)'", error_message)
        if match:
            return match.group(1)
        return None

    def run(self, url, project_name, version=""):
        cloned_repo_path = None
        temp_venv_path = None
        try:
            cloned_repo_path = project_name
            temp_venv_path = os.path.join(cloned_repo_path, ".venv_docs")
            final_output_dir = self.docset_dir / project_name / version
            tmp_output_dir = self.docset_dir / f"tmp_{project_name}" / version

            self.cleanup_folder([project_name, temp_venv_path, final_output_dir, tmp_output_dir])
            self.git_clone(url, project_name)
            venv.create(temp_venv_path, with_pip=True, clear=True)
            _venv_python_rel = os.path.join(temp_venv_path, "bin", "python")
            if sys.platform == "win32":
                _venv_python_rel = os.path.join(temp_venv_path, "Scripts", "python.exe")

            venv_python_interpreter = os.path.abspath(_venv_python_rel)

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
            print("qua")
            original_sys_path_inner = list(sys.path)

            sys.path.insert(0, venv_site_packages)
            print(f"Added {venv_site_packages} a sys.path")
            try:
                print("Esecuzione generate_docs_from_folder con venv sys.path...")
                success = self.generate_docs_from_folder(
                    cloned_repo_path, tmp_output_dir, modules_to_document=[project_name], venv_python_interpreter=venv_python_interpreter
                )

                if success:
                    print(
                        f"Generazione documentation completed con successo per {project_name}"
                    )
                    if os.path.exists(final_output_dir):
                        shutil.rmtree(final_output_dir)
                    shutil.move(tmp_output_dir, final_output_dir)
                else:
                    print(
                        "Generazione documentation failed o nessun modulo documentato "
                        f"per {project_name}"
                    )

            finally:
                sys.path = original_sys_path_inner
                print(f"Removed {venv_site_packages} da sys.path")
                if os.path.exists(tmp_output_dir):
                    self.cleanup_folder(tmp_output_dir)
        except subprocess.CalledProcessError as cpe:
            print(f"\nERROR durante l'esecuzione di un comando pip: {cpe.cmd}")
            print(f"Codice di uscita: {cpe.returncode}")
            print(f"Output del comando (stdout):\n---\n{cpe.stdout}\n---")
            print(f"Errors del comando (stderr):\n---\n{cpe.stderr}\n---")
        except RuntimeError as e:
            print(f"\nERROR durante la fase di clonazione: {e}")
        except Exception as e:
            print(f"\nUnexpected ERROR durante il process: {e}")

            print("--- TRACEBACK ---")
            traceback.print_exc()
            print("--- FINE DETTAGLIO ERROR IMPREVISTO ---")
        finally:
            print("Pulizia delle temporary folders...")
            if cloned_repo_path and temp_venv_path:
                self.cleanup_folder([cloned_repo_path, temp_venv_path])
            print("Pulizia delle temporanee folders completed.")


if __name__ == "__main__":
    P_URL = "https://github.com/psf/black"
    p_name = P_URL.split("/")[-1]
    d_src = DocStringsSrc()
    d_src.run(P_URL, p_name)
