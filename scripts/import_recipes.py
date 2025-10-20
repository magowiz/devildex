"""Recipe importer module."""
import argparse
import json
import logging
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

from devildex.database.db_manager import DatabaseManager, init_db
from devildex.database.models import PackageInfo, ProjectDocRequirements

logger = logging.getLogger(__name__)


class RecipeImporter:
    """Class to import documentation recipes into the DevilDex database."""

    def __init__(self, db_session: Session) -> None:
        """Initialize the RecipeImporter."""
        self.db_session = db_session

    @staticmethod
    def _load_json_from_path(file_path: Path) -> list[dict[str, Any]] | None:
        """Load JSON data from a local file path."""
        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.exception(f"Failed to load JSON from {file_path}")
            return None

    def _fetch_json_from_url(self, url: str) -> list[dict[str, Any]] | None:
        """Fetch JSON data from a URL."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            logger.exception(f"Failed to fetch JSON from {url}")
            return None
        except json.JSONDecodeError:
            logger.exception(f"Failed to decode JSON from {url}")
            return None

    def save_project_doc_requirements(
        self,
        package_name: str,
        builder_type: str,
        requirements: list[str],
        version_range: str | None = None,
        source_url: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """Save or updates ProjectDocRequirements in the database."""
        # Ensure PackageInfo exists
        package_info = (
            self.db_session.query(PackageInfo)
            .filter_by(package_name=package_name)
            .first()
        )
        if not package_info:
            package_info = PackageInfo(package_name=package_name)
            self.db_session.add(package_info)
            self.db_session.flush()  # Assigns primary key to package_info
        # Find or create ProjectDocRequirements
        doc_req = (
            self.db_session.query(ProjectDocRequirements)
            .filter_by(package_name=package_name, builder_type=builder_type)
            .first()
        )
        if doc_req:
            doc_req.requirements = requirements
            doc_req.version_range = version_range
            doc_req.source_url = source_url
            doc_req.notes = notes
            logger.info(
                f"Updated ProjectDocRequirements for {package_name} ({builder_type})"
            )
        else:
            doc_req = ProjectDocRequirements(
                package_name=package_name,
                builder_type=builder_type,
                requirements=requirements,
                version_range=version_range,
                source_url=source_url,
                notes=notes,
            )
            self.db_session.add(doc_req)
            logger.info(
                f"Added new ProjectDocRequirements for {package_name} ({builder_type})"
            )
            try:
                self.db_session.commit()
            except Exception:
                self.db_session.rollback()
                logger.exception(
                    f"Error saving ProjectDocRequirements for {package_name}"
                    f" ({builder_type})"
                )
                return False
            else:
                return True

    def import_recipes(self, source: str | Path) -> bool:
        """Import documentation recipes from a local file path or a URL.

        Recipes are then saved/updated in the database.

        """
        recipes_data: list[dict[str, Any]] | None = None
        if isinstance(source, Path):
            recipes_data = self._load_json_from_path(source)
        elif isinstance(source, str) and (
            source.startswith("http://") or source.startswith("https://")
        ):
            recipes_data = self._fetch_json_from_url(source)
        else:
            logger.error(
                f"Invalid source type or format: {source}. "
                "Must be a Path or a URL string."
            )
            return False
        if not recipes_data:
            logger.warning(f"No recipes data found from source: {source}")
            return False
        success_count = 0
        for recipe in recipes_data:
            package_name = recipe.get("package_name")
            builder_type = recipe.get("builder_type")
            requirements = recipe.get("requirements")
            version_range = recipe.get("version_range")
            source_url = recipe.get("source_url")
            notes = recipe.get("notes")
            if not all([package_name, builder_type, requirements]):
                logger.warning(f"Skipping malformed recipe: {recipe}")
                continue
            if self.save_project_doc_requirements(
                package_name=package_name,
                builder_type=builder_type,
                requirements=requirements,
                version_range=version_range,
                source_url=source_url,
                notes=notes,
            ):
                success_count += 1
            else:
                logger.error(
                    f"Failed to save recipe for {package_name} ({builder_type})"
                )
        logger.info(
            f"Successfully imported {success_count} out of"
            f" {len(recipes_data)} recipes from {source}"
        )
        return success_count > 0


def main() -> None:
    """Execute the script."""
    parser = argparse.ArgumentParser(
        description="Import documentation recipes into the DevilDex database."
    )
    parser.add_argument(
        "source",
        type=str,
        help="Path to a local JSON file or a URL to a JSON file containing recipes.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=f"sqlite:///{Path.home()}/.local/share/devildex/devildex.db",
        help="Database URL for DevilDex (e.g., sqlite:///path/to/devildex.db).",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    init_db(database_url=args.db_url)
    db_manager = DatabaseManager(database_url=args.db_url)
    importer = RecipeImporter(db_session=db_manager.get_session())
    source_path_or_url: str | Path
    if Path(args.source).exists():
        source_path_or_url = Path(args.source)
    else:
        source_path_or_url = args.source
    if importer.import_recipes(source_path_or_url):
        logger.info("Recipe import process completed successfully.")
    else:
        logger.error("Recipe import process failed.")


if __name__ == "__main__":
    main()
