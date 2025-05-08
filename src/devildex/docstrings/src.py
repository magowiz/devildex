"""docstrings pdoc3 module."""

import os
import shutil
import subprocess
import sys
import traceback
import venv
from types import ModuleType

import pdoc

CONFIG_FILE = "../../../devildex_config.ini"


def generate_docs_from_folder(
    input_folder: str, output_folder: str, modules_to_document: list[str] | None = None
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
            try:
                module_obj: ModuleType = pdoc.import_module(
                    name, reload=False, skip_errors=True
                )

                if not hasattr(module_obj, "__file__") and not hasattr(
                    module_obj, "__name__"
                ):
                    print(
                        f"WARNING: L'importazione di '{name}' è fallita "
                        "(import_module con skip_errors=True "
                        "ha ritornato un dummy). Saltato."
                    )
                    continue

                wrapped_modules.append(pdoc.Module(module_obj, context=context))
                print(f"Importato e wrappato: {name}")
            except Exception as e:
                print(
                    "AVVISO: Errore imprevisto durante l'importazione o wrapping di "
                    f"'{name}': {e.__class__.__name__}: {e}"
                )

        if not wrapped_modules:
            print(
                "Nessun modulo è stato importato correttamente dopo aver tentato l'importazione "
                "dei nomi trovati/specificati."
            )
            return False

        pdoc.link_inheritance(context)
        print("Collegamento ereditarietà completed.")

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


def cleanup_folder(folder):
    if isinstance(folder, list):
        for f in folder:
            cleanup_folder(f)
        return

    if os.path.isdir(folder):
        shutil.rmtree(folder)


def git_clone(repo_url, clone_dir_path, default_branch="master"):
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


def run(url, project_name, version=""):
    cloned_repo_path = None
    temp_venv_path = None
    try:
        cloned_repo_path = project_name
        temp_venv_path = os.path.join(cloned_repo_path, ".venv_docs")
        final_output_dir = os.path.join("../../../docset", project_name, version)
        tmp_output_dir = os.path.join("../../../docset", "tmp" + project_name, version)
        cleanup_folder([project_name, temp_venv_path, final_output_dir, tmp_output_dir])
        git_clone(url, project_name)
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
            success = generate_docs_from_folder(
                cloned_repo_path, tmp_output_dir, modules_to_document=[project_name]
            )

            if success:
                print(
                    f"Generazione documentation completata con successo per {project_name}"
                )
                if os.path.exists(final_output_dir):
                    shutil.rmtree(final_output_dir)
                shutil.move(tmp_output_dir, final_output_dir)
            else:
                print(
                    "Generazione documentation fallita o nessun modulo documentato "
                    f"per {project_name}"
                )

        finally:
            sys.path = original_sys_path_inner
            print(f"Removed {venv_site_packages} da sys.path")
            if os.path.exists(tmp_output_dir):
                cleanup_folder(tmp_output_dir)
    except subprocess.CalledProcessError as cpe:
        print(f"\nERROR durante l'esecuzione di un comando pip: {cpe.cmd}")
        print(f"Codice di uscita: {cpe.returncode}")
        print(f"Output del comando (stdout):\n---\n{cpe.stdout}\n---")
        print(f"Errors del comando (stderr):\n---\n{cpe.stderr}\n---")
    except RuntimeError as e:
        print(f"\nERROR durante la fase di clonazione: {e}")
    except Exception as e:
        print(f"\nERROR imprevisto durante il process: {e}")

        print("--- TRACEBACK ---")
        traceback.print_exc()
        print("--- FINE DETTAGLIO ERROR IMPREVISTO ---")
    finally:
        print("Pulizia delle cartelle temporanee...")
        if cloned_repo_path and temp_venv_path:
            cleanup_folder([cloned_repo_path, temp_venv_path])
        print("Pulizia delle temporanee folders completed.")


if __name__ == "__main__":
    P_URL = "https://github.com/psf/black"
    p_name = P_URL.split("/")[-1]
    run(P_URL, p_name)
