"""models module."""

import datetime
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

project_docset_association = Table(
    "project_docset_association",
    Base.metadata,
    Column(
        "project_id", Integer, ForeignKey("registered_project.id"), primary_key=True
    ),
    Column("docset_id", Integer, ForeignKey("docset.id"), primary_key=True),
)


@dataclass
class PackageDetails:
    """Contains details of a  software package."""

    name: str
    version: str | None
    project_urls: dict[str, str] = field(default_factory=dict)
    initial_source_path: Path | str | None = None
    vcs_url: str | None = None
    rtd_url: str | None = None
    status: str = "unknown"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackageDetails":
        """Create an instance of PackageDetails from a dictionary."""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            project_urls=data.get("project_urls", {}),
            initial_source_path=data.get("initial_source_path"),
            vcs_url=data.get("vcs_url"),
            rtd_url=data.get("rtd_url"),
        )


class PackageInfo(Base):  # type: ignore[valid-type,misc]
    """Model for general package information, common across versions."""

    __tablename__ = "package_info"

    package_name = Column(String, primary_key=True, index=True)
    summary = Column(Text, nullable=True)
    _project_urls_json = Column("project_urls", Text, nullable=True)

    docsets = relationship("Docset", back_populates="package_info")

    @property
    def project_urls(self) -> dict[str, str]:
        """Get project_urls come dictionary."""
        if self._project_urls_json:
            try:

                return json.loads(
                    self._project_urls_json
                )  # type: ignore[no-any-return]
            except json.JSONDecodeError:

                logger = logging.getLogger(__name__)
                logger.exception(
                    "Error nel decoding project_urls JSON per package_info "
                    f"{self.package_name}: "
                    f"{self._project_urls_json}"
                )
                return {}
        return {}

    @project_urls.setter
    def project_urls(self, value: dict[str, str]) -> None:
        """Set up project_urls, converting it in JSON."""
        if value:

            self._project_urls_json = json.dumps(value)
        else:
            self._project_urls_json = None

    def __repr__(self) -> str:
        """Implement repr method."""
        return f"<PackageInfo(name='{self.package_name}')>"


class RegisteredProject(Base):  # type: ignore[valid-type,misc]
    """Model for registered project."""

    __tablename__ = "registered_project"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_name = Column(String, unique=True, nullable=False, index=True)
    project_path = Column(String, unique=True, nullable=False)
    python_executable = Column(String, nullable=False, index=True)
    registration_timestamp_utc = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    docsets = relationship(
        "Docset",
        secondary=project_docset_association,
        back_populates="associated_projects",
    )

    def __repr__(self) -> str:
        """Implement repr method."""
        return (
            f"<RegisteredProject(id={self.id}, "
            f"name='{self.project_name}', python_exec='{self.python_executable}')>"
        )


class Docset(Base):  # type: ignore[valid-type,misc]
    """Model for docset, specific to a package version."""

    __tablename__ = "docset"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    package_name = Column(
        String, ForeignKey("package_info.package_name"), nullable=False, index=True
    )
    package_version = Column(String, nullable=False, index=True)

    index_file_name = Column(String, nullable=False, default="index.html")
    generation_timestamp_utc = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    status = Column(String, nullable=False, default="unknown")
    notes = Column(Text, nullable=True)

    package_info = relationship("PackageInfo", back_populates="docsets")

    associated_projects = relationship(
        "RegisteredProject",
        secondary=project_docset_association,
        back_populates="docsets",
    )

    __table_args__ = (
        UniqueConstraint(
            "package_name", "package_version", name="uq_docset_package_name_version"
        ),
    )

    def __repr__(self) -> str:
        """Implement repr method."""
        return (
            f"<Docset(id={self.id}, name='{self.package_name}', "
            f"version='{self.package_version}')>"
        )


class ProjectDocRequirements(Base):  # type: ignore[valid-type,misc]
    """Model for project-specific documentation build requirements."""

    __tablename__ = "project_doc_requirements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    package_name = Column(
        String, ForeignKey("package_info.package_name"), nullable=False, index=True
    )
    builder_type = Column(String, nullable=False, index=True)
    _requirements_json = Column("requirements_json", Text, nullable=True)

    package_info = relationship("PackageInfo", backref="doc_requirements")

    __table_args__ = (
        UniqueConstraint(
            "package_name", "builder_type", name="uq_project_doc_requirements"
        ),
    )

    @property
    def requirements(self) -> list[str]:
        """Get requirements as a list of strings."""
        if self._requirements_json:
            try:
                return json.loads(self._requirements_json)
            except json.JSONDecodeError:
                logger = logging.getLogger(__name__)
                logger.exception(
                    f"Error decoding requirements JSON for {self.package_name} "
                    f"builder {self.builder_type}: {self._requirements_json}"
                )
                return []
        return []

    @requirements.setter
    def requirements(self, value: list[str]) -> None:
        """Set requirements, converting it to JSON."""
        if value:
            self._requirements_json = json.dumps(value)
        else:
            self._requirements_json = None

    def __repr__(self) -> str:
        """Implement repr method."""
        return (
            f"<ProjectDocRequirements(id={self.id}, "
            f"package_name='{self.package_name}', "
            f"builder_type='{self.builder_type}')>"
        )
