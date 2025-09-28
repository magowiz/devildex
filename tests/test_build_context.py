from pathlib import Path
import shutil
from unittest.mock import MagicMock, patch

import pytest

from devildex.orchestrator.context import BuildContext


@pytest.fixture
def mock_build_context(tmp_path: Path) -> BuildContext:
    """Fixture for a BuildContext instance."""
    """Fixture for a BuildContext instance."""
    return BuildContext(
        project_name="test_project",
        project_version="1.0.0",
        base_output_dir=tmp_path / "base_output",
        vcs_url="https://github.com/test/test_project.git",
    )


def test_build_context_init(tmp_path: Path) -> None:
    """Test BuildContext initialization."""
    base_output = tmp_path / "my_base_output"
    context = BuildContext(
        project_name="my_project",
        project_version="2.0.0",
        base_output_dir=base_output,
        vcs_url="https://github.com/my/my_project.git",
    )

    assert context.project_name == "my_project"
    assert context.project_version == "2.0.0"
    assert context.base_output_dir == base_output.resolve()
    assert context.vcs_url == "https://github.com/my/my_project.git"
    assert context.temp_dir == base_output.resolve() / "_temp"
    assert context.final_docs_dir == base_output.resolve() / "my_project" / "2.0.0"
    assert context.source_root is None
    assert context.doc_source_root is None
    assert context.sphinx_conf_py is None
    assert context.mkdocs_yml is None


def test_setup_directories(mock_build_context: BuildContext) -> None:
    """Test setup_directories creates and cleans directories."""
    mock_build_context.setup_directories()

    assert mock_build_context.temp_dir.is_dir()
    assert mock_build_context.final_docs_dir.is_dir()

    # Test cleaning existing directories
    (mock_build_context.temp_dir / "old_file.txt").touch()
    (mock_build_context.final_docs_dir / "old_doc.html").touch()
    mock_build_context.setup_directories()
    assert not (mock_build_context.temp_dir / "old_file.txt").exists()
    assert not (mock_build_context.final_docs_dir / "old_doc.html").exists()


def test_resolve_package_source_path_no_source_root(
    mock_build_context: BuildContext,
) -> None:
    """Test resolve_package_source_path when source_root is not set."""
    mock_build_context.source_root = None
    result = mock_build_context.resolve_package_source_path("any_project")
    assert result is None


def test_resolve_package_source_path_direct_package(tmp_path: Path) -> None:
    """Test resolve_package_source_path with a direct package."""
    project_root = tmp_path / "my_project_src"
    project_root.mkdir()
    (project_root / "my_package").mkdir()
    (project_root / "my_package" / "__init__.py").touch()

    context = BuildContext(
        project_name="my_project",
        project_version="1.0.0",
        base_output_dir=tmp_path / "output",
        source_root=project_root,
    )
    result = context.resolve_package_source_path("my_package")
    assert result == (project_root / "my_package").resolve()


def test_resolve_package_source_path_src_package(tmp_path: Path) -> None:
    """Test resolve_package_source_path with a package in 'src'."""
    project_root = tmp_path / "my_project_src"
    (project_root / "src" / "my_package").mkdir(parents=True)
    (project_root / "src" / "my_package" / "__init__.py").touch()

    context = BuildContext(
        project_name="my_project",
        project_version="1.0.0",
        base_output_dir=tmp_path / "output",
        source_root=project_root,
    )
    result = context.resolve_package_source_path("my_package")
    assert result == (project_root / "src" / "my_package").resolve()


def test_resolve_package_source_path_root_is_package(tmp_path: Path) -> None:
    """Test resolve_package_source_path when root itself is a package."""
    project_root = tmp_path / "my_package"
    project_root.mkdir()
    (project_root / "__init__.py").touch()

    context = BuildContext(
        project_name="my_package",
        project_version="1.0.0",
        base_output_dir=tmp_path / "output",
        source_root=project_root,
    )
    result = context.resolve_package_source_path("my_package")
    assert result == project_root.resolve()


def test_resolve_package_source_path_single_module_file(tmp_path: Path) -> None:
    """Test resolve_package_source_path with a single module file."""
    project_root = tmp_path / "my_project_src"
    project_root.mkdir()
    (project_root / "my_module.py").touch()

    context = BuildContext(
        project_name="my_module",
        project_version="1.0.0",
        base_output_dir=tmp_path / "output",
        source_root=project_root,
    )
    result = context.resolve_package_source_path("my_module")
    assert result == project_root.resolve()


def test_resolve_package_source_path_no_package_found(tmp_path: Path) -> None:
    """Test resolve_package_source_path when no package is found."""
    project_root = tmp_path / "my_project_src"
    project_root.mkdir()
    (project_root / "random.txt").touch()

    context = BuildContext(
        project_name="non_existent_package",
        project_version="1.0.0",
        base_output_dir=tmp_path / "output",
        source_root=project_root,
    )
    result = context.resolve_package_source_path("non_existent_package")
    assert result is None


def test_resolve_package_source_path_project_name_variations(tmp_path: Path) -> None:
    """Test resolve_package_source_path with project name variations."""
    project_root = tmp_path / "my-project-dash-src"
    project_root.mkdir()
    (project_root / "my_project_dash.py").touch() # Matches my-project-dash -> my_project_dash

    context = BuildContext(
        project_name="my-project-dash",
        project_version="1.0.0",
        base_output_dir=tmp_path / "output",
        source_root=project_root,
    )
    result = context.resolve_package_source_path("my-project-dash")
    assert result == project_root.resolve()

    (project_root / "another_module.py").touch()
    context_another = BuildContext(
        project_name="Another-Module",
        project_version="1.0.0",
        base_output_dir=tmp_path / "output",
        source_root=project_root,
    )
    result_another = context_another.resolve_package_source_path("Another-Module")
    assert result_another == project_root.resolve()
