"""Test mkdocs builder."""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from pytest_mock import MockerFixture

from devildex.grabbers.mkdocs_builder import (
    MkDocsBuilder,
    _find_mkdocs_config_file,
    _find_mkdocs_doc_requirements_file,
    _gather_mkdocs_required_packages,
    _parse_mkdocs_config,
)
from devildex.orchestrator.context import BuildContext

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_build_context(tmp_path: Path) -> BuildContext:
    """Fixture for a mock BuildContext."""
    return BuildContext(
        project_name="test-mkdocs-project",
        project_version="1.0.0",
        base_output_dir=tmp_path / "output",
        source_root=tmp_path / "source",
        vcs_url="http://example.com/repo",
        project_slug="test-mkdocs-project",
        version_identifier="1.0.0",
        project_root_for_install=tmp_path / "source",
    )


@pytest.fixture
def mkdocs_project_setup(tmp_path: Path) -> Path:
    """Set up a basic MkDocs project in a temporary directory."""
    project_path = tmp_path / "mkdocs_project"
    project_path.mkdir()
    (project_path / "mkdocs.yml").write_text(
        """
site_name: Test Project
theme: readthedocs
plugins:
  - search
markdown_extensions:
  - admonition
"""
    )
    (project_path / "docs").mkdir()
    (project_path / "docs" / "index.md").write_text("# Hello MkDocs")
    return project_path


@pytest.fixture
def mkdocs_project_with_requirements(mkdocs_project_setup: Path) -> Path:
    """Set up an MkDocs project with a requirements.txt file."""
    (mkdocs_project_setup / "requirements.txt").write_text("mkdocs-material\n")
    return mkdocs_project_setup


def create_mkdocs_yml(path: Path, content: dict | None = None) -> None:
    """Create a mkdocs.yml file with the given content."""
    if content is None:
        content = {"site_name": "Test Site"}
    path.mkdir(parents=True, exist_ok=True)
    (path / "mkdocs.yml").write_text(yaml.dump(content))


class TestMkDocsBuilder:
    """Test mkdocs builder."""

    def test_can_handle_true(
        self, mkdocs_project_setup: Path, mock_build_context: BuildContext
    ) -> None:
        """Test can_handle returns True for a valid MkDocs project."""
        builder = MkDocsBuilder()
        assert builder.can_handle(mkdocs_project_setup, mock_build_context) is True

    def test_can_handle_false(
        self, tmp_path: Path, mock_build_context: BuildContext
    ) -> None:
        """Test can_handle returns False for a non-MkDocs project."""
        non_mkdocs_project = tmp_path / "non_mkdocs_project"
        non_mkdocs_project.mkdir()
        builder = MkDocsBuilder()
        assert builder.can_handle(non_mkdocs_project, mock_build_context) is False

    def test_generate_docset_success(
        self,
        mocker: MockerFixture,
        mkdocs_project_with_requirements: Path,
        mock_build_context: BuildContext,
        tmp_path: Path,
    ) -> None:
        """Test generate_docset successfully builds documentation."""
        builder = MkDocsBuilder()

        # Mock internal helper methods that are now part of the builder
        mock_find_config = mocker.patch(
            "devildex.grabbers.mkdocs_builder._find_mkdocs_config_file",
            return_value=mkdocs_project_with_requirements / "mkdocs.yml",
        )
        mock_parse_config = mocker.patch(
            "devildex.grabbers.mkdocs_builder._parse_mkdocs_config",
            return_value={"site_name": "Test Project", "theme": "readthedocs"},
        )
        mock_gather_packages = mocker.patch(
            "devildex.grabbers.mkdocs_builder._gather_mkdocs_required_packages",
            return_value=["mkdocs"],
        )
        mock_venv_instance = MagicMock()
        mock_venv_instance.python_executable = str(Path("/mock/venv/bin/python"))
        mock_venv_instance.pip_executable = str(Path("/mock/venv/bin/pip"))
        mock_venv_manager = mocker.patch(
            "devildex.grabbers.mkdocs_builder.IsolatedVenvManager"
        )
        mock_venv_manager.return_value.__enter__.return_value = mock_venv_instance
        mock_install_deps = mocker.patch(
            "devildex.grabbers.mkdocs_builder.install_project_and_dependencies_in_venv",
            return_value=True,
        )

        # Mock execute_command for mkdocs build
        mock_execute_command = mocker.patch(
            "devildex.grabbers.mkdocs_builder.execute_command",
            return_value=("stdout", "stderr", 0),
        )

        output_path = tmp_path / "build_output"
        mock_build_context.base_output_dir = output_path
        mock_build_context.project_root_for_install = mkdocs_project_with_requirements

        result = builder.generate_docset(
            mkdocs_project_with_requirements, output_path, mock_build_context
        )

        assert result is True
        assert (
            output_path
            / mock_build_context.project_slug
            / mock_build_context.version_identifier
        ).exists()
        mock_find_config.assert_called_once_with(mkdocs_project_with_requirements)
        mock_parse_config.assert_called_once()
        mock_gather_packages.assert_called_once()
        mock_install_deps.assert_called_once_with(
            pip_executable=mock_venv_instance.pip_executable,
            project_name=mock_build_context.project_slug,
            project_root_for_install=mock_build_context.project_root_for_install,
            doc_requirements_path=_find_mkdocs_doc_requirements_file(
                mkdocs_project_with_requirements,
                mock_build_context.project_root_for_install,
                mock_build_context.project_slug,
            ),
            base_packages_to_install=mock_gather_packages.return_value,
        )
        mock_execute_command.assert_called_once()
        args, kwargs = mock_execute_command.call_args
        assert "mkdocs" in args[0]
        assert "build" in args[0]
        # The MkDocsBuilder now uses a temporary config file, so assert against that.
        # The temporary config file path is passed as '--config-file /tmp/tmpXXXXXX.yml'
        config_file_arg_index = args[0].index("--config-file") + 1
        temp_config_file_path_in_command = args[0][config_file_arg_index]
        assert "tmp" in temp_config_file_path_in_command
        assert ".yml" in temp_config_file_path_in_command
        assert (
            str(
                (
                    output_path
                    / mock_build_context.project_slug
                    / mock_build_context.version_identifier
                ).resolve()
            )
            in args[0]
        )
        assert kwargs["cwd"] == mkdocs_project_with_requirements

    def test_generate_docset_build_failure(
        self,
        mocker: MockerFixture,
        mkdocs_project_setup: Path,
        mock_build_context: BuildContext,
        tmp_path: Path,
    ) -> None:
        """Test generate_docset returns False when mkdocs build command fails."""
        builder = MkDocsBuilder()

        # Mock internal helper methods
        mocker.patch(
            "devildex.grabbers.mkdocs_builder._find_mkdocs_config_file",
            return_value=mkdocs_project_setup / "mkdocs.yml",
        )
        mocker.patch(
            "devildex.grabbers.mkdocs_builder._parse_mkdocs_config",
            return_value={"site_name": "Test Project", "theme": "readthedocs"},
        )
        mocker.patch(
            "devildex.grabbers.mkdocs_builder._gather_mkdocs_required_packages",
            return_value=["mkdocs"],
        )

        # Mock venv manager and install functions
        mock_venv_instance = MagicMock()
        mock_venv_instance.python_executable = str(Path("/mock/venv/bin/python"))
        mock_venv_instance.pip_executable = str(Path("/mock/venv/bin/pip"))
        mock_venv_manager = mocker.patch(
            "devildex.grabbers.mkdocs_builder.IsolatedVenvManager"
        )
        mock_venv_manager.return_value.__enter__.return_value = mock_venv_instance
        mocker.patch(
            "devildex.grabbers.mkdocs_builder.install_project_and_dependencies_in_venv",
            return_value=True,
        )

        # Mock execute_command to simulate failure
        mocker.patch(
            "devildex.grabbers.mkdocs_builder.execute_command",
            return_value=("stdout", "stderr", 1),
        )

        output_path = tmp_path / "build_output"
        mock_build_context.base_output_dir = output_path

        result = builder.generate_docset(
            mkdocs_project_setup, output_path, mock_build_context
        )

        assert result is False

    def test_generate_docset_no_mkdocs_yml(
        self, tmp_path: Path, mock_build_context: BuildContext
    ) -> None:
        """Test generate_docset returns False if mkdocs.yml is not found."""
        builder = MkDocsBuilder()
        source_path = tmp_path / "empty_project"
        source_path.mkdir()

        result = builder.generate_docset(
            source_path, tmp_path / "output", mock_build_context
        )

        assert result is False

    def test_find_mkdocs_doc_requirements_file_found(
        self, mkdocs_project_with_requirements: Path
    ) -> None:
        """Test _find_mkdocs_doc_requirements_file finds requirements.txt."""
        result = _find_mkdocs_doc_requirements_file(
            mkdocs_project_with_requirements,
            mkdocs_project_with_requirements,
            "test_project",
        )
        assert result == mkdocs_project_with_requirements / "requirements.txt"

    def test_find_mkdocs_doc_requirements_file_not_found(
        self, mkdocs_project_setup: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test _find_mkdocs_doc_requirements_file returns None if no file is found."""
        with caplog.at_level(logging.INFO):
            result = _find_mkdocs_doc_requirements_file(
                mkdocs_project_setup, mkdocs_project_setup, "test_project"
            )
        assert result is None
        assert "No specific 'requirements.txt' found for documentation" in caplog.text

    def test_gather_mkdocs_required_packages_basic(self, mocker: MockerFixture) -> None:
        """Test _gather_mkdocs_required_packages with basic config."""
        config = {"site_name": "Test", "theme": "readthedocs"}
        packages = _gather_mkdocs_required_packages(config)
        assert "mkdocs" in packages
        assert "mkdocs-material" not in packages  # readthedocs is built-in

    def test_gather_mkdocs_required_packages_material_theme(
        self, mocker: MockerFixture
    ) -> None:
        """Test _gather_mkdocs_required_packages with material theme."""
        config = {"site_name": "Test", "theme": "material"}
        packages = _gather_mkdocs_required_packages(config)
        assert "mkdocs" in packages
        assert "mkdocs-material" in packages

    def test_gather_mkdocs_required_packages_plugins(
        self, mocker: MockerFixture
    ) -> None:
        """Test _gather_mkdocs_required_packages with plugins."""
        config = {
            "site_name": "Test",
            "plugins": [
                "search",
                {
                    "mkdocstrings": {
                        "handlers": {"python": {"options": {"show_root_heading": True}}}
                    }
                },
            ],
            "markdown_extensions": ["pymdownx.highlight", "admonition"],
        }
        packages = _gather_mkdocs_required_packages(config)
        assert "mkdocs" in packages
        assert "mkdocstrings[python]" in packages
        assert "pymdown-extensions" in packages
        assert "ruff" in packages  # Because mkdocstrings is present
        assert "search" not in packages  # Built-in
        assert "admonition" not in packages  # Built-in

    def test_find_mkdocs_config_file_root(self, tmp_path: Path) -> None:
        """Test _find_mkdocs_config_file finds config in root."""
        (tmp_path / "mkdocs.yml").touch()
        assert _find_mkdocs_config_file(tmp_path) == (tmp_path / "mkdocs.yml")

    def test_find_mkdocs_config_file_docs_subdir(self, tmp_path: Path) -> None:
        """Test _find_mkdocs_config_file finds config in docs subdir."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "mkdocs.yml").touch()
        assert _find_mkdocs_config_file(tmp_path) == (tmp_path / "docs" / "mkdocs.yml")

    def test_find_mkdocs_config_file_not_found(self, tmp_path: Path) -> None:
        """Test _find_mkdocs_config_file returns None if not found."""
        assert _find_mkdocs_config_file(tmp_path) is None

    def test_parse_mkdocs_config_success(self, tmp_path: Path) -> None:
        """Test _parse_mkdocs_config successfully parses a valid config."""
        config_content = "site_name: Test\ntheme: readthedocs"
        config_file = tmp_path / "mkdocs.yml"
        config_file.write_text(config_content)
        parsed_config = _parse_mkdocs_config(config_file)
        assert parsed_config == {"site_name": "Test", "theme": "readthedocs"}

    def test_parse_mkdocs_config_invalid_yaml(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test _parse_mkdocs_config handles invalid YAML."""
        config_content = "site_name: - Test\ntheme: readthedocs"
        config_file = tmp_path / "mkdocs.yml"
        config_file.write_text(config_content)
        with caplog.at_level(logging.ERROR):
            parsed_config = _parse_mkdocs_config(config_file)
        assert parsed_config is None
        assert "Error parsing MkDocs Config file" in caplog.text

    def test_parse_mkdocs_config_file_not_found(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test _parse_mkdocs_config handles file not found."""
        non_existent_file = tmp_path / "non_existent.yml"
        with caplog.at_level(logging.ERROR):
            parsed_config = _parse_mkdocs_config(non_existent_file)
        assert parsed_config is None
        assert "Error reading MkDocs Config file" in caplog.text
