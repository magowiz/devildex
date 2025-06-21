"""script to compare themes."""

import argparse
import logging
import shutil
import subprocess
import tempfile
import webbrowser
from argparse import Namespace
from pathlib import Path

from devildex.docstrings.docstrings_src import DocStringsSrc
from devildex.info import PROJECT_ROOT as DEVILDEX_PROJECT_ROOT
from devildex.mkdocs.mkdocs_src import (
    process_mkdocs_source_and_build,
)
from devildex.readthedocs.readthedocs_src import (
    CONF_SPHINX_FILE,
)
from devildex.theming.manager import ThemeManager
from devildex.utils.venv_cm import IsolatedVenvManager, VenvInitializationError
from devildex.utils.venv_utils import (
    InstallConfig,
    execute_command,
    install_environment_dependencies,
)

SPHINX_COMMON_PACKAGES = [
    "sphinx",
    "pallets-sphinx-themes",
    "sphinxcontrib.log-cabinet",
    "sphinx-tabs",
]

SUPPORTED_TYPES = ["sphinx", "pdoc3", "mkdocs"]
KNOWN_PROJECTS = {
    "black": {
        "repo_url": "https://github.com/psf/black.git",
        "doc_type": "sphinx",
        "doc_source_path_relative": "docs/",
        "default_branch": "main",
    },
    "flask": {
        "repo_url": "https://github.com/pallets/flask.git",
        "doc_type": "sphinx",
        "doc_source_path_relative": "docs/",
        "default_branch": "main",
    },
    "fastapi": {
        "repo_url": "https://github.com/tiangolo/fastapi.git",
        "doc_type": "pdoc3",
        "module_name": "fastapi",
        "default_branch": "master",
    },
    "mkdocs": {
        "repo_url": "https://github.com/mkdocs/mkdocs.git",
        "doc_type": "mkdocs",
        "default_branch": "master",
    },
}

PDOC3_DEVILDEX_THEME_PATH = (
    DEVILDEX_PROJECT_ROOT / "src" / "devildex" / "theming" / "devildex_pdoc3_theme"
)

logger = logging.getLogger("theme_comparator")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def clone_repository(repo_url: str, target_dir: Path, branch: str) -> bool:
    """Clona un repository nella cartella target, provando il branch specificato."""
    if target_dir.exists():
        logger.info(f"Pulizia della cartella di clone esistente: {target_dir}")
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    git_executable = shutil.which("git")
    if not git_executable:
        logger.error("Git non trovato. Assicurati che sia installato e nel PATH.")
        return False

    cmd = [git_executable, "clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([repo_url, str(target_dir)])

    logger.info(
        f"Tentativo di clonare {repo_url} (branch: "
        f"{branch or 'default'}) in {target_dir}..."
    )
    process = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, check=False, encoding="utf-8"
    )

    if process.returncode == 0:
        logger.info("Clonazione riuscita.")
        return True
    else:
        logger.error(
            f"Clonazione fallita. Branch: {branch or 'default'}. "
            f"Stderr: {process.stderr.strip()}"
        )
        if branch and branch not in [
            "main",
            "master",
        ]:
            logger.info("Tentativo di clonare il branch di default...")
            return clone_repository(repo_url, target_dir, "main")
        return False


def build_sphinx_vanilla(
    project_slug: str,
    cloned_repo_path: Path,
    doc_source_relative_path: str,
    output_base_dir: Path,
) -> Path | None:
    """Build Sphinx con il tema originale del progetto."""
    logger.info(f"--- Build Sphinx VANILLA per {project_slug} ---")
    doc_source_absolute_path = (cloned_repo_path / doc_source_relative_path).resolve()
    vanilla_output_dir = (output_base_dir / f"{project_slug}_sphinx_vanilla").resolve()

    if not (doc_source_absolute_path / CONF_SPHINX_FILE).exists():
        logger.error(
            f"File conf.py di Sphinx non trovato in {doc_source_absolute_path}"
        )
        return None

    try:
        with IsolatedVenvManager(project_name=f"{project_slug}_sphinx_vanilla") as venv:
            current_tool_specific_packages = SPHINX_COMMON_PACKAGES
            install_conf = InstallConfig(
                project_root_for_install=cloned_repo_path,
                tool_specific_packages=current_tool_specific_packages,
                scan_for_project_requirements=True,
                install_project_editable=True,
            )
            if not install_environment_dependencies(
                venv.pip_executable, f"{project_slug}_vanilla_deps", install_conf
            ):
                logger.error(
                    "Installazione dipendenze fallita per build Sphinx vanilla."
                )
                return None

            if vanilla_output_dir.exists():
                shutil.rmtree(vanilla_output_dir)
            vanilla_output_dir.mkdir(parents=True, exist_ok=True)

            sphinx_command = [
                venv.python_executable,
                "-m",
                "sphinx",
                "-b",
                "html",
                str(doc_source_absolute_path),
                str(vanilla_output_dir),
            ]
            logger.info(f"Esecuzione build Sphinx vanilla: {' '.join(sphinx_command)}")
            _stdout, stderr_out, ret_code = execute_command(
                sphinx_command,
                f"Build Sphinx vanilla per {project_slug}",
                cwd=str(doc_source_absolute_path),
            )
            if ret_code == 0 and (vanilla_output_dir / "index.html").exists():
                logger.info(f"Build Sphinx vanilla riuscita: {vanilla_output_dir}")
                return vanilla_output_dir
            else:
                logger.error(
                    f"Build Sphinx vanilla fallita. RC: {ret_code}\n"
                    f"Stderr:\n{stderr_out}"
                )
                return None
    except (VenvInitializationError, RuntimeError):
        logger.exception("Errore durante la build Sphinx vanilla")
        return None


def _guard_sphinx(
    cloned_repo_path: Path,
    doc_source_relative_path: str,
    output_base_dir: Path,
    project_slug: str,
) -> tuple | None:
    original_doc_source_path = (cloned_repo_path / doc_source_relative_path).resolve()
    devil_output_dir = (output_base_dir / f"{project_slug}_sphinx_devil").resolve()

    temp_devil_doc_source = output_base_dir / f"{project_slug}_temp_devil_docs_src"
    if temp_devil_doc_source.exists():
        shutil.rmtree(temp_devil_doc_source)
    shutil.copytree(original_doc_source_path, temp_devil_doc_source)
    devil_conf_py_file = temp_devil_doc_source / CONF_SPHINX_FILE

    if not devil_conf_py_file.exists():
        logger.error(
            "File conf.py di Sphinx non trovato nella copia "
            f"temporanea: {devil_conf_py_file}"
        )
        if temp_devil_doc_source.exists():
            shutil.rmtree(temp_devil_doc_source)
        return None
    return devil_conf_py_file, temp_devil_doc_source, devil_output_dir


def build_sphinx_devil(
    project_slug: str,
    cloned_repo_path: Path,
    doc_source_relative_path: str,
    output_base_dir: Path,
) -> Path | None:
    """Build Sphinx con il tema DevilDex."""
    logger.info(f"--- Build Sphinx DEVIL per {project_slug} ---")
    devil_conf_py_file, temp_devil_doc_source, devil_output_dir = _guard_sphinx(
        cloned_repo_path=cloned_repo_path,
        doc_source_relative_path=doc_source_relative_path,
        output_base_dir=output_base_dir,
        project_slug=project_slug,
    )

    try:
        theme_manager = ThemeManager(
            project_path=cloned_repo_path,
            doc_type="sphinx",
            sphinx_conf_file=devil_conf_py_file,
        )
        theme_manager.sphinx_change_conf()
        logger.info(f"Tema DevilDex applicato a: {devil_conf_py_file}")

        with IsolatedVenvManager(project_name=f"{project_slug}_sphinx_devil") as venv:
            install_conf = InstallConfig(
                project_root_for_install=cloned_repo_path,
                tool_specific_packages=SPHINX_COMMON_PACKAGES,
                scan_for_project_requirements=True,
                install_project_editable=True,
            )
            if not install_environment_dependencies(
                venv.pip_executable, f"{project_slug}_devil_deps", install_conf
            ):
                logger.error("Installazione dipendenze fallita per build Sphinx Devil.")
                if temp_devil_doc_source.exists():
                    shutil.rmtree(temp_devil_doc_source)
                return None

            if devil_output_dir.exists():
                shutil.rmtree(devil_output_dir)
            devil_output_dir.mkdir(parents=True, exist_ok=True)

            sphinx_command = [
                venv.python_executable,
                "-m",
                "sphinx",
                "-b",
                "html",
                "-c",
                str(temp_devil_doc_source),
                str(temp_devil_doc_source),
                str(devil_output_dir),
            ]
            logger.info(f"Esecuzione build Sphinx Devil: {' '.join(sphinx_command)}")
            _stdout, stderr_out, ret_code = execute_command(
                sphinx_command,
                f"Build Sphinx Devil per {project_slug}",
                cwd=str(temp_devil_doc_source),
            )

            if temp_devil_doc_source.exists():
                shutil.rmtree(temp_devil_doc_source)

            if ret_code == 0 and (devil_output_dir / "index.html").exists():
                logger.info(f"Build Sphinx Devil riuscita: {devil_output_dir}")
                return devil_output_dir
            else:
                logger.error(
                    f"Build Sphinx Devil fallita. RC: {ret_code}\nStderr:\n{stderr_out}"
                )
                return None
    except (VenvInitializationError, RuntimeError):
        logger.exception("Errore durante la build Sphinx Devil")
        if temp_devil_doc_source.exists():
            shutil.rmtree(temp_devil_doc_source)
        return None


def build_pdoc3_vanilla(
    project_slug: str,
    cloned_repo_path: Path,
    module_name: str,
    output_base_dir: Path,
) -> Path | None:
    """Build pdoc3 con il tema di default."""
    logger.info(
        f"--- Build pdoc3 VANILLA per {project_slug} (modulo: {module_name}) ---"
    )
    vanilla_output_dir = (output_base_dir / f"{project_slug}_pdoc3_vanilla").resolve()
    temp_pdoc_build_target = (
        output_base_dir / f"{project_slug}_pdoc3_vanilla_temp_build"
    )

    doc_generator = DocStringsSrc(template_dir=None)
    result_path_str = doc_generator.generate_docs_from_folder(
        project_name=module_name,
        input_folder=str(cloned_repo_path.resolve()),
        output_folder=str(temp_pdoc_build_target.resolve()),
    )

    if isinstance(result_path_str, str):
        if vanilla_output_dir.exists():
            shutil.rmtree(vanilla_output_dir)
        shutil.move(result_path_str, vanilla_output_dir)
        logger.info(f"Build pdoc3 vanilla riuscita: {vanilla_output_dir}")
        if temp_pdoc_build_target.exists() and not any(
            temp_pdoc_build_target.iterdir()
        ):
            shutil.rmtree(temp_pdoc_build_target)
        return vanilla_output_dir
    else:
        logger.error("Build pdoc3 vanilla fallita.")
        if temp_pdoc_build_target.exists():
            shutil.rmtree(temp_pdoc_build_target)
        return None


def build_pdoc3_devil(
    project_slug: str,
    cloned_repo_path: Path,
    module_name: str,
    output_base_dir: Path,
) -> Path | None:
    """Build pdoc3 con il tema DevilDex."""
    logger.info(f"--- Build pdoc3 DEVIL per {project_slug} (modulo: {module_name}) ---")
    devil_output_dir = (output_base_dir / f"{project_slug}_pdoc3_devil").resolve()
    temp_pdoc_build_target = output_base_dir / f"{project_slug}_pdoc3_devil_temp_build"

    doc_generator = DocStringsSrc(template_dir=PDOC3_DEVILDEX_THEME_PATH)
    result_path_str = doc_generator.generate_docs_from_folder(
        project_name=module_name,
        input_folder=str(cloned_repo_path.resolve()),
        output_folder=str(temp_pdoc_build_target.resolve()),
    )

    if isinstance(result_path_str, str):
        if devil_output_dir.exists():
            shutil.rmtree(devil_output_dir)
        shutil.move(result_path_str, devil_output_dir)
        logger.info(f"Build pdoc3 Devil riuscita: {devil_output_dir}")
        if temp_pdoc_build_target.exists() and not any(
            temp_pdoc_build_target.iterdir()
        ):
            shutil.rmtree(temp_pdoc_build_target)
        return devil_output_dir
    else:
        logger.error("Build pdoc3 Devil fallita.")
        if temp_pdoc_build_target.exists():
            shutil.rmtree(temp_pdoc_build_target)
        return None


def build_mkdocs_vanilla(
    project_slug: str,
    cloned_repo_path: Path,
    output_base_dir: Path,
    version_id: str = "vanilla",
) -> Path | None:
    """Build MkDocs con la configurazione originale."""
    logger.info(f"--- Build MkDocs VANILLA per {project_slug} ---")
    vanilla_output_dir = (output_base_dir / f"{project_slug}_mkdocs_vanilla").resolve()
    temp_base_for_mkdocs_build = (
        output_base_dir / f"{project_slug}_mkdocs_vanilla_temp_base"
    )

    built_path_str = process_mkdocs_source_and_build(
        source_project_path=str(cloned_repo_path.resolve()),
        project_slug=project_slug,
        version_identifier=version_id,
        base_output_dir=temp_base_for_mkdocs_build,
    )
    if built_path_str:
        if vanilla_output_dir.exists():
            shutil.rmtree(vanilla_output_dir)
        shutil.move(built_path_str, vanilla_output_dir)
        logger.info(f"Build MkDocs vanilla riuscita: {vanilla_output_dir}")
        if temp_base_for_mkdocs_build.exists():
            shutil.rmtree(temp_base_for_mkdocs_build)
        return vanilla_output_dir
    else:
        logger.error("Build MkDocs vanilla fallita.")
        if temp_base_for_mkdocs_build.exists():
            shutil.rmtree(temp_base_for_mkdocs_build)
        return None


def build_mkdocs_devil(
    project_slug: str,
    cloned_repo_path: Path,
    output_base_dir: Path,
    version_id: str = "devil",
) -> Path | None:
    """Build MkDocs (placeholder per il tema DevilDex)."""
    logger.info(f"--- Build MkDocs DEVIL per {project_slug} ---")
    devil_output_dir = (output_base_dir / f"{project_slug}_mkdocs_devil").resolve()
    temp_base_for_mkdocs_build = (
        output_base_dir / f"{project_slug}_mkdocs_devil_temp_base"
    )
    logger.warning(
        "La build MkDocs Devil non applica ancora un tema DevilDex "
        "specifico. Esegue una build standard."
    )

    # Per ora, esegue una build standard come vanilla.
    built_path_str = process_mkdocs_source_and_build(
        source_project_path=str(cloned_repo_path.resolve()),
        project_slug=project_slug,
        version_identifier=version_id,
        base_output_dir=temp_base_for_mkdocs_build,
    )
    if built_path_str:
        if devil_output_dir.exists():
            shutil.rmtree(devil_output_dir)
        shutil.move(built_path_str, devil_output_dir)
        logger.info(f"Build MkDocs Devil (standard) riuscita: {devil_output_dir}")
        if temp_base_for_mkdocs_build.exists():
            shutil.rmtree(temp_base_for_mkdocs_build)
        return devil_output_dir
    else:
        logger.error("Build MkDocs Devil (standard) fallita.")
        if temp_base_for_mkdocs_build.exists():
            shutil.rmtree(temp_base_for_mkdocs_build)
        return None


def find_entry_point(
    built_docs_path: Path, doc_type: str, module_name_for_pdoc: str | None = None
) -> Path | None:
    """Trova il file index.html o l'equivalente."""
    if not built_docs_path.exists():
        return None

    index_html = built_docs_path / "index.html"
    if index_html.is_file():
        return index_html

    if doc_type == "pdoc3" and module_name_for_pdoc:
        module_html = built_docs_path / f"{module_name_for_pdoc}.html"
        if module_html.is_file():
            return module_html

    logger.warning(
        f"File index.html non trovato in {built_docs_path} per tipo {doc_type}."
    )
    html_files = list(built_docs_path.glob("*.html"))
    if html_files:
        logger.info(f"Trovato un file HTML alternativo: {html_files[0]}")
        return html_files[0]
    return None


def pdoc3_run(
    module_name_for_pdoc: str | None,
    args: Namespace,
    cloned_repo_path: Path,
    build_outputs_base_dir: Path,
    run_temp_dir: Path,
) -> tuple[Path | None, Path | None] | None:
    """Run pdoc3 build."""
    vanilla_entry_point: Path | None = None
    devil_entry_point: Path | None = None
    if not module_name_for_pdoc:
        logger.error(
            "Configurazione 'module_name' mancante per pdoc3"
            f" per il progetto {args.project_name}"
        )
        if not args.keep_builds:
            shutil.rmtree(run_temp_dir)
        return None
    if not args.skip_vanilla:
        vanilla_built_path = build_pdoc3_vanilla(
            args.project_name,
            cloned_repo_path,
            module_name_for_pdoc,
            build_outputs_base_dir,
        )
        if vanilla_built_path:
            vanilla_entry_point = find_entry_point(
                vanilla_built_path, "pdoc3", module_name_for_pdoc
            )
    if not args.skip_devil:
        devil_built_path = build_pdoc3_devil(
            args.project_name,
            cloned_repo_path,
            module_name_for_pdoc,
            build_outputs_base_dir,
        )
        if devil_built_path:
            devil_entry_point = find_entry_point(
                devil_built_path, "pdoc3", module_name_for_pdoc
            )
    return vanilla_entry_point, devil_entry_point


def mkdocs_run(
    args: Namespace,
    cloned_repo_path: Path,
    build_outputs_base_dir: Path,
    branch_to_clone: str,
) -> tuple[str | None, str | None]:
    """Run mkdocs build."""
    vanilla_entry_point: Path | None = None
    devil_entry_point: Path | None = None
    if not args.skip_vanilla:
        vanilla_built_path = build_mkdocs_vanilla(
            args.project_name,
            cloned_repo_path,
            build_outputs_base_dir,
            version_id=branch_to_clone,
        )
        if vanilla_built_path:
            vanilla_entry_point = find_entry_point(vanilla_built_path, "mkdocs")
    if not args.skip_devil:
        devil_built_path = build_mkdocs_devil(
            args.project_name,
            cloned_repo_path,
            build_outputs_base_dir,
            version_id=branch_to_clone,
        )
        if devil_built_path:
            devil_entry_point = find_entry_point(devil_built_path, "mkdocs")
    return vanilla_entry_point, devil_entry_point


def sphinx_run(
    project_config: dict,
    args: Namespace,
    cloned_repo_path: Path,
    build_outputs_base_dir: Path,
) -> tuple[Path | None, Path | None] | None:
    """Run Sphinx build."""
    vanilla_entry_point: Path | None = None
    devil_entry_point: Path | None = None
    doc_source_rel = project_config.get("doc_source_path_relative", "docs/")
    if not args.skip_vanilla:
        vanilla_built_path = build_sphinx_vanilla(
            args.project_name,
            cloned_repo_path,
            doc_source_rel,
            build_outputs_base_dir,
        )
        if vanilla_built_path:
            vanilla_entry_point = find_entry_point(vanilla_built_path, "sphinx")
    if not args.skip_devil:
        devil_built_path = build_sphinx_devil(
            args.project_name,
            cloned_repo_path,
            doc_source_rel,
            build_outputs_base_dir,
        )
        if devil_built_path:
            devil_entry_point = find_entry_point(devil_built_path, "sphinx")
    return vanilla_entry_point, devil_entry_point

def _configure_arg_parser() -> argparse.ArgumentParser:
    """Configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Compara temi di documentazione originali e DevilDex."
    )
    parser.add_argument(
        "project_name",
        choices=list(KNOWN_PROJECTS.keys()),
        help="Nome del progetto da processare (deve essere in KNOWN_PROJECTS).",
    )
    parser.add_argument(
        "--doc-type",
        choices=SUPPORTED_TYPES,
        help="Forza un tipo di documentazione specifico. "
        "Sovrascrive il default del progetto.",
    )
    parser.add_argument(
        "--branch",
        help="Branch specifico da clonare. Default: 'main' o il default del progetto.",
    )
    parser.add_argument(
        "--keep-builds",
        action="store_true",
        help="Conserva le cartelle di build temporanee dopo l'esecuzione.",
    )

    # --- INIZIO MODIFICA ---
    # Gruppo per gestire le build in modo esclusivo
    build_group = parser.add_mutually_exclusive_group()
    build_group.add_argument(
        "--only",
        choices=["vanilla", "devil"],
        help="Esegue solo la build specificata (vanilla o devil).",
    )
    build_group.add_argument(
        "--skip-vanilla",
        action="store_true",
        help="Salta la build della documentazione vanilla.",
    )
    build_group.add_argument(
        "--skip-devil",
        action="store_true",
        help="Salta la build della documentazione DevilDex.",
    )
    # --- FINE MODIFICA ---
    return parser



def _guards(args: Namespace, project_config: dict) -> tuple | None:
    if not project_config:
        logger.error(f"Progetto '{args.project_name}' non trovato in KNOWN_PROJECTS.")
        return None

    doc_type_to_build = args.doc_type or project_config["doc_type"]
    repo_url = project_config["repo_url"]
    branch_to_clone = args.branch or project_config.get("default_branch", "main")

    run_temp_dir = Path(tempfile.mkdtemp(prefix=f"theme_compare_{args.project_name}_"))
    logger.info(f"Directory temporanea per questa esecuzione: {run_temp_dir}")

    cloned_repo_path = run_temp_dir / "source_clone"
    build_outputs_base_dir = run_temp_dir / "build_outputs"
    build_outputs_base_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"Clonazione di {args.project_name} da {repo_url} (branch: {branch_to_clone})"
    )
    if not clone_repository(repo_url, cloned_repo_path, branch_to_clone):
        logger.error("Clonazione repository fallita. Interruzione.")
        if not args.keep_builds:
            shutil.rmtree(run_temp_dir)
        return None
    return (
        doc_type_to_build,
        build_outputs_base_dir,
        cloned_repo_path,
        run_temp_dir,
        branch_to_clone,
    )


def main() -> None:
    """Run Main method."""
    parser = _configure_arg_parser()
    args = parser.parse_args()
    project_config = KNOWN_PROJECTS.get(args.project_name)
    if args.only == "devil":
        args.skip_vanilla = True
    elif args.only == "vanilla":
        args.skip_devil = True
    res = _guards(args=args, project_config=project_config)
    if not res:
        return
    (
        doc_type_to_build,
        build_outputs_base_dir,
        cloned_repo_path,
        run_temp_dir,
        branch_to_clone,
    ) = res
    module_name_for_pdoc = project_config.get("module_name")

    if doc_type_to_build == "sphinx":
        vanilla_entry_point, devil_entry_point = sphinx_run(
            project_config=project_config,
            build_outputs_base_dir=build_outputs_base_dir,
            cloned_repo_path=cloned_repo_path,
            args=args,
        )

    elif doc_type_to_build == "pdoc3":
        vanilla_entry_point, devil_entry_point = pdoc3_run(
            args=args,
            run_temp_dir=run_temp_dir,
            cloned_repo_path=cloned_repo_path,
            module_name_for_pdoc=module_name_for_pdoc,
            build_outputs_base_dir=build_outputs_base_dir,
        )

    elif doc_type_to_build == "mkdocs":
        vanilla_entry_point, devil_entry_point = mkdocs_run(
            args=args,
            cloned_repo_path=cloned_repo_path,
            build_outputs_base_dir=build_outputs_base_dir,
            branch_to_clone=branch_to_clone,
        )
    else:
        logger.error(f"Tipo di documentazione non supportato: {doc_type_to_build}")
        if not args.keep_builds:
            shutil.rmtree(run_temp_dir)
        return

    if vanilla_entry_point and vanilla_entry_point.exists():
        logger.info(f"Apertura documentazione VANILLA: {vanilla_entry_point.as_uri()}")
        webbrowser.open_new(vanilla_entry_point.as_uri())
    elif not args.skip_vanilla:
        logger.warning(
            "Punto di ingresso documentazione vanilla non trovato o build fallita."
        )

    if devil_entry_point and devil_entry_point.exists():
        logger.info(f"Apertura documentazione DEVIL: {devil_entry_point.as_uri()}")
        webbrowser.open_new(devil_entry_point.as_uri())
    elif not args.skip_devil:
        logger.warning(
            "Punto di ingresso documentazione Devil non trovato o build fallita."
        )

    logger.info("Script di comparazione temi terminato.")


if __name__ == "__main__":
    main()
