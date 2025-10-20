"""core module."""

import logging
import shutil
import threading
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from devildex.app_paths import AppPaths
from devildex.config_manager import ConfigManager
from devildex.database import db_manager as database
from devildex.database.models import Docset, PackageDetails
from devildex.local_data_parse import registered_project_parser
from devildex.local_data_parse.common_read import (
    get_explicit_dependencies_from_project_config,
)
from devildex.local_data_parse.external_venv_scanner import (
    ExternalVenvScanner,
)
from devildex.local_data_parse.registered_project_parser import RegisteredProjectData
from devildex.mcp_server.mcp_server_manager import McpServerManager
from devildex.orchestrator.documentation_orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DevilDexCore:
    """DevilDex Core."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        gui_warning_callback: Optional[Callable] = None,
        docset_base_output_path: Optional[Path] = None,
    ) -> None:
        """Initialize a new DevilDexCore instance."""
        self.app_paths = AppPaths()
        self.database_url = database_url or f"sqlite:///{self.app_paths.database_path}"
        self.docset_base_output_path: Optional[Path] = None
        self.registered_project_name: Optional[str] = None
        self.registered_project_path: Optional[str] = None
        self.registered_project_python_executable: Optional[str] = None
        self.mcp_server_manager: Optional[McpServerManager] = None
        self._tasks: dict[str, dict[str, Any]] = {}
        self.gui_warning_callback = gui_warning_callback

        if docset_base_output_path:
            self.set_docset_base_output_path(docset_base_output_path)
        else:
            self.docset_base_output_path = self.app_paths.docsets_base_dir
            self._setup_registered_project()

    def set_docset_base_output_path(self, path: Path) -> None:
        """Set the base output path for docsets and initialize components."""
        self.docset_base_output_path = path
        self.docset_base_output_path.mkdir(parents=True, exist_ok=True)
        self.registered_project_name = None
        self.registered_project_path = None
        self.registered_project_python_executable = None
        self._setup_registered_project()

    def shutdown(self) -> None:
        """Shut down the core services."""
        self.stop_mcp_server()

    def _run_generation_task(
        self, task_id: str, package_data: dict, force: bool
    ) -> None:
        """Run docset generation in a separate thread."""
        self._tasks[task_id]["status"] = TaskStatus.RUNNING
        package_name = package_data.get("name")

        try:
            validation_result = self._validate_generation_inputs(
                task_id, package_data, force
            )
            if not validation_result:
                return

            package_name, package_version, project_urls = validation_result

            details = PackageDetails(
                name=str(package_name),
                version=str(package_version),
                project_urls=project_urls if isinstance(project_urls, dict) else {},
            )

            orchestrator = self._execute_orchestration(task_id, details)
            if not orchestrator:
                return

            generation_result = orchestrator.grab_build_doc()
            self._process_generation_result(
                task_id, generation_result, orchestrator, details
            )

        except Exception as e:
            logger.exception(
                "Core: An unexpected error occurred during docset generation"
                f" for {package_name}."
            )
            self._tasks[task_id]["result"] = (False, f"Unexpected error: {e!s}")
            self._tasks[task_id]["status"] = TaskStatus.FAILED

    def _validate_generation_inputs(
        self, task_id: str, package_data: dict, force: bool
    ) -> Optional[tuple[str, str, dict]]:
        """Validate inputs for docset generation."""
        package_name = package_data.get("name")
        package_version = package_data.get("version")
        project_urls = package_data.get("project_urls")

        if not package_name or not package_version:
            error_msg = "missing package name or version nei dati di input."
            self._tasks[task_id]["result"] = (False, error_msg)
            self._tasks[task_id]["status"] = TaskStatus.FAILED
            return None

        logger.info(
            f"Core: Validating generation inputs for {package_name} v{package_version}. "
            f"Force regeneration: {force}"
        )
        existing_docsets = self.search_for_docset(package_name, package_version)
        logger.info(f"Core: Found existing docsets (status 'COMPLETED'): {existing_docsets}")
        if existing_docsets and not force:
            logger.info(
                f"Core: Docset for {package_name} v{package_version} already exists "
                "and force is False. Aborting generation."
            )
            self._tasks[task_id]["result"] = (
                False,
                f"Docset for {package_name} v{package_version} already exists. "
                "Use force=True to regenerate.",
            )
            self._tasks[task_id]["status"] = TaskStatus.COMPLETED
            return None

        return str(package_name), str(package_version), project_urls

    def _execute_orchestration(
        self, task_id: str, details: PackageDetails
    ) -> Optional[Orchestrator]:
        """Create and run the orchestrator."""
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
            self._tasks[task_id]["result"] = (False, msg)
            self._tasks[task_id]["status"] = TaskStatus.FAILED
            return None
        return orchestrator

    def _process_generation_result(
        self,
        task_id: str,
        generation_result: Union[str, bool],
        orchestrator: Orchestrator,
        details: PackageDetails,
    ) -> None:
        """Process the result of the docset generation."""
        if isinstance(generation_result, str):
            self._tasks[task_id]["result"] = (True, generation_result)
            self._tasks[task_id]["status"] = TaskStatus.COMPLETED
            self._update_database_on_success(
                details.name, details.version, details.project_urls
            )
        elif not generation_result:
            last_op_detail = orchestrator.get_last_operation_result()
            error_msg = f"Failure nella generation del docset per {details.name}."
            if isinstance(last_op_detail, str) and last_op_detail:
                error_msg += f" Details: {last_op_detail}"
            elif last_op_detail is False:
                error_msg += " Specified operation is failed."
            self._tasks[task_id]["result"] = (False, error_msg)
            self._tasks[task_id]["status"] = TaskStatus.FAILED
        else:
            unexpected_msg = (
                f"Unexpected result ({type(generation_result)}) "
                f"dalla generation del docset per {details.name}."
            )
            self._tasks[task_id]["result"] = (False, unexpected_msg)
            self._tasks[task_id]["status"] = TaskStatus.FAILED

    @staticmethod
    def _update_database_on_success(
        package_name: str, package_version: str, project_urls: dict
    ) -> None:
        """Update the database after a successful docset generation."""
        with database.get_session() as session:
            docset = (
                session.query(database.Docset)
                .filter_by(package_name=package_name, package_version=package_version)
                .first()
            )
            if docset:
                docset.status = TaskStatus.COMPLETED.value
            else:
                package_info = (
                    session.query(database.PackageInfo)
                    .filter_by(package_name=package_name)
                    .first()
                )
                if not package_info:
                    package_info = database.PackageInfo(
                        package_name=package_name,
                        summary="",
                        project_urls=project_urls,
                    )
                    session.add(package_info)

                docset = database.Docset(
                    package_name=package_name,
                    package_version=package_version,
                    status=TaskStatus.COMPLETED.value,
                    package_info=package_info,
                )
                session.add(docset)
            session.commit()

    @staticmethod
    def query_project_names() -> list[str]:
        """Retrieve only the NAMES of all registered projects from the database."""
        logger.info("Core: Requesting list of project names from the DB...")
        project_names = database.DatabaseManager.get_all_project_names()
        logger.info(f"Core: Received {len(project_names)} project names.")
        return project_names

    def set_active_project(self, project_name: Optional[str]) -> bool:
        """Set the specified project as active in the core."""
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
        """Scan the active project's virtual environment for installed packages."""
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

    @staticmethod
    def delete_docset_build(docset_path_str: str) -> tuple[bool, str]:
        """Delete a docset build directory and its parent if empty."""
        try:
            path_of_specific_docset_build = Path(docset_path_str)
            if (
                not path_of_specific_docset_build.exists()
                or not path_of_specific_docset_build.is_dir()
            ):
                msg = (
                    f"Docset path does not exist or is not a directory: "
                    f"{docset_path_str}"
                )
                logger.warning(msg)
                return False, msg

            package_level_docset_dir = path_of_specific_docset_build.parent
            shutil.rmtree(path_of_specific_docset_build)
            logger.info(
                f"Successfully deleted docset build: {path_of_specific_docset_build}"
            )

            if (
                package_level_docset_dir.exists()
                and package_level_docset_dir.is_dir()
                and not any(package_level_docset_dir.iterdir())
            ):
                shutil.rmtree(package_level_docset_dir)
                logger.info(
                    "Parent directory was empty and has been deleted:"
                    f" {package_level_docset_dir}"
                )

        except OSError as e:
            error_msg = f"Failed to delete docset at {docset_path_str}. Error: {e}"
            logger.exception(error_msg)
            return False, str(e)
        else:
            return True, f"Successfully deleted {path_of_specific_docset_build.name}."

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
        """Initialize the database, populates it with initial data."""
        logger.info("Core: Initializing database...")
        db_url = self.database_url or f"sqlite:///{self.app_paths.database_path}"

        if (
            database.DatabaseManager._engine is None
            or str(database.DatabaseManager._engine.url) != db_url
        ):
            database.init_db(database_url=db_url)
            logger.info("Core: Database initialized.")
        else:
            logger.info("Core: Database already initialized and bound to correct URL.")
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
                    "initial_docset_status": pkg_detail.status,
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
        with database.get_session() as session:
            docsets_to_load_from_db = self._bootstrap_database_read_db(
                project_db_name, session
            )
            grid_data_to_return = self._bootstrap_database_loop_docsets(
                docsets_to_load_from_db
            )
        return grid_data_to_return

    @staticmethod
    def _bootstrap_database_read_db(
        project_db_name: str, session: Session
    ) -> list[Docset]:
        docsets_to_load_from_db: list[database.Docset] = []
        if project_db_name:
            current_project_obj = (
                session.query(database.RegisteredProject)
                .filter_by(project_name=project_db_name)
                .first()
            )
            if current_project_obj:
                docsets_to_load_from_db = list(current_project_obj.docsets)
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
            docsets_to_load_from_db = list(
                session.scalars(select(database.Docset)).all()
            )
            logger.info(
                "Core: No active project, loading all "
                f"{len(docsets_to_load_from_db)} docsets from DB."
            )
        return docsets_to_load_from_db

    @staticmethod
    def _bootstrap_database_loop_docsets(
        docsets_to_load_from_db: list[Docset],
    ) -> list[dict[str, Any]]:
        grid_data_to_return: list[dict[str, Any]] = []
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
        """List i nomi delle directory di primo level nella folder base dei docset."""
        if (
            not self.docset_base_output_path
            or not self.docset_base_output_path.exists()
        ):
            return []
        return [d.name for d in self.docset_base_output_path.iterdir() if d.is_dir()]

    def get_docset_path(
        self, package_name: str, version: Optional[str] = None
    ) -> Optional[Path]:
        """Construct and return the path to a specific docset."""
        if not self.docset_base_output_path:
            return None
        base_path = self.docset_base_output_path / package_name
        if version:
            docset_path = base_path / version
            if docset_path.is_dir():
                return docset_path
            else:
                logger.warning(
                    f"Docset path for {package_name} version {version} "
                    f"not found at {docset_path}"
                )
                return None

        if (base_path / "index.html").is_file():
            return base_path

        for subdir in base_path.iterdir():
            if subdir.is_dir() and (subdir / "index.html").is_file():
                logger.info(
                    f"Auto-detected docset in subdirectory: {subdir.name} "
                    f"for package {package_name}"
                )
                return subdir

        logger.warning(
            f"No docset found for package {package_name} at {base_path} "
            f"or its immediate subdirectories."
        )
        return None

    @staticmethod
    def get_all_docsets_info() -> list[dict[str, Any]]:
        """Retrieve information for all docsets from the database."""
        with database.get_session() as session:
            docsets = session.scalars(select(database.Docset)).all()
            return [
                {
                    "name": d.package_name,
                    "version": d.package_version,
                    "status": d.status,
                }
                for d in docsets
            ]

    @staticmethod
    def get_docsets_info_for_project(project_name: str) -> list[dict[str, Any]]:
        """Retrieve information for docsets associated with a specific project."""
        with database.get_session() as session:
            docsets = session.scalars(
                select(database.Docset)
                .join(database.Docset.associated_projects)
                .where(database.RegisteredProject.project_name == project_name)
            ).all()
            return [
                {
                    "name": d.package_name,
                    "version": d.package_version,
                    "status": d.status,
                }
                for d in docsets
            ]

    def search_for_docset(
        self, package_name: str, version: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Search for docsets matching the given package name and optional version."""
        with database.get_session() as session:
            query = select(database.Docset).where(
                database.Docset.package_name == package_name,
                database.Docset.status == "Completed",
            )
            if version:
                query = query.where(database.Docset.package_version == version)
            docsets = session.scalars(query).all()
            valid_docsets = []
            for d in docsets:
                docset_path = self.get_docset_path(d.package_name, d.package_version)
                if docset_path:
                    valid_docsets.append(
                        {
                            "name": d.package_name,
                            "version": d.package_version,
                            "path": str(docset_path),
                            "status": d.status,
                        }
                    )
            return valid_docsets

    def delete_docset(self, package_name: str, version: Optional[str] = None) -> bool:
        """Delete a docset from the database and its corresponding files."""
        with database.get_session() as session:
            query = select(database.Docset).where(
                database.Docset.package_name == package_name
            )
            if version:
                query = query.where(database.Docset.package_version == version)
            docsets_to_delete = session.scalars(query).all()

            if not docsets_to_delete:
                logger.warning(
                    f"Core: No docset found for deletion for package '{package_name}' "
                    f"version '{version or 'any'}'."
                )
                return False

            for docset in docsets_to_delete:
                path_to_delete = self.get_docset_path(
                    docset.package_name, docset.package_version
                )
                if path_to_delete and path_to_delete.exists():
                    success, msg = self.delete_docset_build(str(path_to_delete))
                    if not success:
                        logger.error(
                            "Core: Failed to delete files for docset "
                            f"'{docset.package_name}' "
                            f"version '{docset.package_version}': {msg}"
                        )
                else:
                    logger.warning(
                        f"Core: Docset path not found for '{docset.package_name}' "
                        f"version '{docset.package_version}'. Deleting only from DB."
                    )

                session.delete(docset)
                logger.info(
                    f"Core: Deleted docset '{docset.package_name}' version "
                    f"'{docset.package_version}' from database."
                )
            session.commit()
            return True

    def generate_docset(self, package_data: dict, force: bool = False) -> str:
        """Initiate asynchronous docset generation and return a task ID."""
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "status": TaskStatus.PENDING,
            "result": None,
            "thread": None,
        }

        thread = threading.Thread(
            target=self._run_generation_task,
            args=(task_id, package_data, force),
        )
        self._tasks[task_id]["thread"] = thread
        thread.start()

        return task_id

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get the status and result of a docset generation task."""
        task_info = self._tasks.get(task_id)
        if task_info is None:
            return {"status": TaskStatus.FAILED.value, "result": "Task not found."}

        thread = task_info.get("thread")
        if (
            thread
            and not thread.is_alive()
            and task_info["status"] == TaskStatus.RUNNING
        ):
            if task_info["result"] and task_info["result"][0]:
                task_info["status"] = TaskStatus.COMPLETED
            else:
                task_info["status"] = TaskStatus.FAILED

        return {
            "status": task_info["status"].value,
            "result": task_info["result"],
        }

    def start_mcp_server_if_enabled(self, db_url: str) -> bool:
        """Start the MCP server if it is enabled in the configuration."""
        config = ConfigManager()
        if config.get_mcp_server_enabled():
            logger.info("Core: MCP server is enabled. Starting...")
            if not self.mcp_server_manager:
                self.mcp_server_manager = McpServerManager()
            server_started = self.mcp_server_manager.start_server(db_url)
            if server_started:
                logger.info("Core: MCP server started successfully.")
                return True
            else:
                logger.error("Core: Failed to start MCP server.")
                return False
        else:
            logger.info("Core: MCP server is disabled. Not starting.")
            return False

    def stop_mcp_server(self) -> None:
        """Stop the MCP server if it is running."""
        if self.mcp_server_manager:
            logger.info("Core: Stopping MCP server...")
            self.mcp_server_manager.stop_server()
            logger.info("Core: MCP server stopped.")
