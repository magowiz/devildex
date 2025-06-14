import logging
import os
from pathlib import Path
from typing import Any, Optional

from devildex import database
from devildex.app_paths import AppPaths
from devildex.local_data_parse import registered_project_parser
from devildex.local_data_parse.common_read import (
    get_explicit_dependencies_from_project_config,
)
from devildex.local_data_parse.external_venv_scanner import ExternalVenvScanner
from devildex.local_data_parse.registered_project_parser import RegisteredProjectData
from devildex.models import PackageDetails
from devildex.orchestrator.documentation_orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class DevilDexCore:
    """DevilDex Core."""

    def __init__(self) -> None:
        """Initialize a new DevilDexCore instance."""
        self.app_paths = AppPaths()
        if os.getenv("DEVILDEX_DEV_MODE") == "1":
            self.docset_base_output_path = Path("devildex_docsets")
            self.database_file_path = Path("devildex_dev.db")
        else:
            self.docset_base_output_path = self.app_paths.docsets_base_dir
            self.database_file_path = self.app_paths.database_path
        self.docset_base_output_path.mkdir(parents=True, exist_ok=True)
        self.registered_project_name: Optional[str] = None
        self.registered_project_path: Optional[str] = None
        self.registered_project_python_executable: Optional[str] = None

        self._setup_registered_project()

    @staticmethod
    def query_project_names() -> list[str]:
        """Retrieve only the NAMES of all registered projects from the database.

        Used to populate the ComboBox in the GUI.
        """
        logger.info("Core: Requesting list of project names from the DB...")
        project_names = database.DatabaseManager.get_all_project_names()
        logger.info(f"Core: Received {len(project_names)} project names.")
        return project_names

    def set_active_project(self, project_name: Optional[str]) -> bool:
        """Set the specified project as active in the core.

        If project_name is None, sets the global view.
        Loads details (path, python_exec) from the DB for the specified project.
        Returns True if the project was set successfully, False otherwise.
        """
        if project_name is None:
            logger.info("Core: Setting global view (no active project).")
            self.registered_project_name = None
            self.registered_project_path = None
            self.registered_project_python_executable = None
            registered_project_parser.clear_active_registered_project()
            return True

        logger.info(f"Core: Attempting to set '{project_name}' as active project.")
        project_details = database.DatabaseManager.get_project_details_by_name(
            project_name
        )
        if project_details:
            p_name = project_details.get("project_name", "")
            p_path = project_details.get("project_path", "")
            p_python_exec = project_details.get("python_executable", "")

            self.registered_project_name = p_name
            self.registered_project_path = p_path
            self.registered_project_python_executable = p_python_exec

            logger.info(
                f"Core: Project '{self.registered_project_name}' "
                f"set as active. "
                f"Path: {self.registered_project_path}, Python: "
                f"{self.registered_project_python_executable}"
            )
            project_data_to_save: RegisteredProjectData = {
                "project_name": p_name,
                "project_path": p_path,
                "python_executable": p_python_exec,
            }
            registered_project_parser.save_active_registered_project(
                project_data_to_save
            )
            return True
        else:
            logger.error(
                f"Core: Could not find details for project '{project_name}' in the DB."
            )
            self.registered_project_name = None
            self.registered_project_path = None
            self.registered_project_python_executable = None
            registered_project_parser.clear_active_registered_project()
            return False

    def scan_project(self) -> list | None:
        """Scan the active project's virtual environment for installed packages.

        If a project is currently registered and active, this method uses its
        configured Python executable to scan its virtual environment.
        It attempts to identify explicit dependencies from project configuration
        files (e.g., pyproject.toml, requirements.txt).

        - If explicit dependencies are found, only those packages (if installed
          in the venv) are returned.
        - If no explicit dependencies are found, all packages from the venv
          are returned.
        - If no project is active, or if the venv scan yields no packages,
          it returns None.

        Returns:
            Optional[list[PackageDetails]]: A list of PackageDetails objects
            representing the found packages, or None if no project is active
            or no packages are found.

        """
        if self.registered_project_name:
            evenv_scanner = ExternalVenvScanner(
                self.registered_project_python_executable
            )
            exp_dep: set[str] = get_explicit_dependencies_from_project_config(
                start_path=self.registered_project_path
            )
            packages = evenv_scanner.scan_packages()
            result = []
            if not packages:
                return None
            elif exp_dep:
                for package in packages:
                    normalized_package_name = package.name.lower().replace("_", "-")
                    if normalized_package_name in exp_dep:
                        result.append(package)
            elif packages:
                result = packages
            return result
        return None

    def load_all_registered_projects_details(self) -> dict:
        """Get all registered project details."""
        return {
            "project_name": self.registered_project_name,
            "project_path": self.registered_project_path,
            "python_executable": self.registered_project_python_executable,
        }

    def _setup_registered_project(self) -> None:
        """Carica i details del project active e li set come attributes."""
        active_project_data = registered_project_parser.load_active_registered_project()
        if active_project_data:
            self.registered_project_name = active_project_data.get("project_name")
            self.registered_project_path = active_project_data.get("project_path")
            self.registered_project_python_executable = active_project_data.get(
                "python_executable"
            )
            logger.info(
                f"Core: Registered project loaded: {self.registered_project_name} "
                f"at {self.registered_project_path}"
            )
        else:
            logger.info("Core: No registered project found.")

    def bootstrap_database_and_load_data(
        self, initial_package_source: list[PackageDetails], is_fallback_data: bool
    ) -> list[dict[str, Any]]:
        """Initialize the database, populates it with initial data.

        and loads data for the grid.
        """
        logger.info("Core: Initializing database...")
        db_url = f"sqlite:///{self.database_file_path}"
        database.init_db(database_url=db_url)
        logger.info("Core: Database initialized.")

        project_db_name = self.registered_project_name
        project_db_path = self.registered_project_path
        project_db_python_exec = self.registered_project_python_executable

        logger.info(
            "Core: Populating DB using initial_package_source - Total:"
            f" {len(initial_package_source)} packages."
        )
        for pkg_detail in initial_package_source:
            pkg_name = pkg_detail.name
            pkg_version = pkg_detail.version
            pkg_summary = getattr(pkg_detail, "summary", None) or getattr(
                pkg_detail, "description", "N/A"
            )
            pkg_project_urls = pkg_detail.project_urls

            if pkg_name and pkg_version:
                logger.debug(f"Core: Processing for DB: {pkg_name} v{pkg_version}")
                build_dict = {
                    "package_name": str(pkg_name),
                    "package_version": str(pkg_version),
                    "summary": str(pkg_summary) if pkg_summary else None,
                    "project_urls": pkg_project_urls,
                    "initial_docset_status": "unknown",
                }
                if not is_fallback_data and project_db_name:
                    build_dict["project_name"] = project_db_name
                    build_dict["project_path"] = project_db_path
                    build_dict["python_executable"] = project_db_python_exec
                database.ensure_package_entities_exist(**build_dict)
            else:
                logger.warning(
                    "Core: Skipped record from initial_package_source due to "
                    f"missing name or version: {pkg_detail}"
                )

        logger.info("Core: Initial DB population completed.")

        logger.info("Core: Loading data from database for the grid...")
        grid_data_to_return: list[dict[str, Any]] = []
        with database.get_session() as session:
            docsets_to_load_from_db: list[database.Docset] = []
            if project_db_name:
                current_project_obj = (
                    session.query(database.RegisteredProject)
                    .filter_by(project_name=project_db_name)
                    .first()
                )
                if current_project_obj:
                    docsets_to_load_from_db = current_project_obj.docsets
                    logger.info(
                        f"Core: Loading {len(docsets_to_load_from_db)} "
                        f"docsets for project '{project_db_name}'."
                    )
                else:
                    logger.warning(
                        f"Core: Project '{project_db_name}' not found in "
                        "DB for loading its docsets."
                    )
            else:
                docsets_to_load_from_db = session.query(database.Docset).all()
                logger.info(
                    "Core: No active project, loading all "
                    f"{len(docsets_to_load_from_db)} docsets from DB."
                )

            for db_docset in docsets_to_load_from_db:
                pkg_info = db_docset.package_info
                grid_row = {
                    "id": db_docset.id,
                    "name": db_docset.package_name,
                    "version": db_docset.package_version,
                    "description": pkg_info.summary if pkg_info else "N/A",
                    "docset_status": db_docset.status,
                }
                if pkg_info and pkg_info.project_urls:
                    grid_row["project_urls"] = pkg_info.project_urls
                grid_data_to_return.append(grid_row)

            logger.info(
                f"Core: Loaded {len(grid_data_to_return)} records from DB for the grid."
            )
        return grid_data_to_return

    def list_package_dirs(self) -> list[str]:
        """List i nomi delle directory di primo level nella folder base dei docset.

        These are potential folders root per i packages.
        """
        if not self.docset_base_output_path.exists():
            return []
        return [d.name for d in self.docset_base_output_path.iterdir() if d.is_dir()]

    def generate_docset(self, package_data: dict) -> tuple[bool, str]:
        """Generate a docset using Orchestrator.

        Returns (success, message).
        """
        package_name = package_data.get("name")
        package_version = package_data.get("version")
        project_urls = package_data.get("project_urls")
        if not package_name or not package_version:
            error_msg = "missing package name or version nei dati di input."
            return False, error_msg
        details = PackageDetails(
            name=str(package_name),
            version=str(package_version),
            project_urls=project_urls if isinstance(project_urls, dict) else {},
        )
        orchestrator = Orchestrator(
            package_details=details, base_output_dir=self.docset_base_output_path
        )
        orchestrator.start_scan()
        detected_type = orchestrator.get_detected_doc_type()
        if detected_type == "unknown":
            last_op_msg = orchestrator.get_last_operation_result()
            msg = f"unable to determine il tipo di documentation per {details.name}."
            if isinstance(last_op_msg, str) and last_op_msg:
                msg += f" Detail: {last_op_msg}"
            return False, msg
        generation_result = orchestrator.grab_build_doc()
        if isinstance(generation_result, str):
            return True, generation_result
        elif not generation_result:
            last_op_detail = orchestrator.get_last_operation_result()
            error_msg = f"Failure nella generation del docset per {details.name}."
            if isinstance(last_op_detail, str) and last_op_detail:
                error_msg += f" Details: {last_op_detail}"
            elif last_op_detail is False:
                error_msg += " Specified operation is failed."
            return False, error_msg
        else:
            unexpected_msg = (
                f"Unexpected result ({type(generation_result)}) "
                f"dalla generation del docset per {details.name}."
            )
            return False, unexpected_msg
