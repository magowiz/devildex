import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from devildex.orchestrator.documentation_orchestrator import Orchestrator
from devildex.models import PackageDetails
from devildex.info import PROJECT_ROOT
from devildex.fetcher import PackageSourceFetcher

@pytest.fixture
def mock_package_details():
    return PackageDetails(
        name="test_package",
        version="1.0.0",
        project_urls={"Source": "https://github.com/test/test_package"},
        vcs_url="https://github.com/test/test_package.git"
    )

@pytest.fixture
def mock_orchestrator(mock_package_details, tmp_path):
    return Orchestrator(
        package_details=mock_package_details,
        base_output_dir=tmp_path / "docset_output"
    )

def test_orchestrator_init(mock_package_details, tmp_path):
    output_dir = tmp_path / "custom_docset_output"
    orchestrator = Orchestrator(
        package_details=mock_package_details,
        base_output_dir=output_dir
    )
    assert orchestrator.package_details == mock_package_details
    assert orchestrator.base_output_dir == output_dir.resolve()
    assert output_dir.exists()
    assert orchestrator.detected_doc_type is None
    assert orchestrator.last_operation_result is None
    assert orchestrator._effective_source_path is None

    # Test with a temporary base_output_dir
    default_output_dir = tmp_path / "default_orchestrator_output"
    orchestrator_default = Orchestrator(
        package_details=mock_package_details,
        base_output_dir=default_output_dir
    )
    assert orchestrator_default.base_output_dir == default_output_dir.resolve()
    assert default_output_dir.exists()

def test_fetch_repo_initial_path_exists(mock_package_details, mock_orchestrator, tmp_path, mocker):
    # Create a real directory for initial_source_path
    initial_source_path = tmp_path / "initial_source"
    initial_source_path.mkdir()
    mock_package_details.initial_source_path = str(initial_source_path)

    result = mock_orchestrator.fetch_repo()

    assert result is True
    assert mock_orchestrator._effective_source_path == initial_source_path.resolve()

def test_fetch_repo_initial_path_does_not_exist(mock_package_details, mock_orchestrator, tmp_path, mocker):
    # Set initial_source_path to a non-existent path
    mock_package_details.initial_source_path = str(tmp_path / "non_existent_path")

    # Create the actual fetched directory
    actual_fetched_path = tmp_path / "fetched_source"
    actual_fetched_path.mkdir()

    # Mock PackageSourceFetcher.fetch to return a successful fetch with a string path
    mock_fetcher_instance = mocker.patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
    mock_fetcher_instance.return_value.fetch.return_value = (True, False, str(actual_fetched_path))

    result = mock_orchestrator.fetch_repo()

    assert result is True
    assert mock_orchestrator._effective_source_path == actual_fetched_path.resolve()

def test_fetch_repo_initial_path_not_a_directory(mock_package_details, mock_orchestrator, tmp_path, mocker):
    # Create a real file for initial_source_path (not a directory)
    initial_source_path = tmp_path / "not_a_dir.txt"
    initial_source_path.touch()
    mock_package_details.initial_source_path = str(initial_source_path)

    # Create the actual fetched directory
    actual_fetched_path = tmp_path / "fetched_source"
    actual_fetched_path.mkdir()

    # Mock PackageSourceFetcher.fetch to return a successful fetch with a string path
    mock_fetcher_instance = mocker.patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
    mock_fetcher_instance.return_value.fetch.return_value = (True, False, str(actual_fetched_path))

    result = mock_orchestrator.fetch_repo()

    assert result is True
    assert mock_orchestrator._effective_source_path == actual_fetched_path.resolve()

def test_fetch_repo_no_initial_path_fetch_succeeds(mock_package_details, mock_orchestrator, tmp_path, mocker):
    mock_package_details.initial_source_path = None

    # Create the actual fetched directory
    actual_fetched_path = tmp_path / "fetched_source"
    actual_fetched_path.mkdir()

    # Mock PackageSourceFetcher.fetch to return a successful fetch with a string path
    mock_fetcher_instance = mocker.patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
    mock_fetcher_instance.return_value.fetch.return_value = (True, False, str(actual_fetched_path))

    result = mock_orchestrator.fetch_repo()

    assert result is True
    assert mock_orchestrator._effective_source_path == actual_fetched_path.resolve()

def test_fetch_repo_no_initial_path_fetch_fails(mock_package_details, mock_orchestrator, mocker):
    mock_package_details.initial_source_path = None
    mock_fetcher_instance = mocker.patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
    mock_fetcher_instance.return_value.fetch.return_value = (False, False, None)

    result = mock_orchestrator.fetch_repo()

    assert result is False
    assert mock_orchestrator._effective_source_path is None

def test_fetch_repo_fetch_raises_os_error(mock_package_details, mock_orchestrator, mocker):
    mock_package_details.initial_source_path = None
    
    # Mock PackageSourceFetcher.fetch to raise OSError
    mock_fetcher_instance = mocker.patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
    mock_fetcher_instance.return_value.fetch.side_effect = OSError("Disk full")

    result = mock_orchestrator.fetch_repo()

    assert result is False
    assert mock_orchestrator._effective_source_path is None

def test_fetch_repo_fetch_raises_runtime_error(mock_package_details, mock_orchestrator, mocker):
    mock_package_details.initial_source_path = None
    
    # Mock PackageSourceFetcher.fetch to raise RuntimeError
    mock_fetcher_instance = mocker.patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
    mock_fetcher_instance.return_value.fetch.side_effect = RuntimeError("Network error")

    result = mock_orchestrator.fetch_repo()

    assert result is False
    assert mock_orchestrator._effective_source_path is None

# Tests for _fetch_repo_fetch method
@patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
def test_internal_fetch_repo_fetch_success(mock_fetcher_class, mock_orchestrator, tmp_path):
    mock_fetcher_instance = mock_fetcher_class.return_value
    mock_fetcher_instance.fetch.return_value = (True, False, str(tmp_path / "fetched_source"))
    
    fetcher_storage_base = tmp_path / "_fetched_project_sources"
    package_info_for_fetcher = {"name": "test_package", "version": "1.0.0", "project_urls": {}}

    result = mock_orchestrator._fetch_repo_fetch(fetcher_storage_base, package_info_for_fetcher)

    assert result == (tmp_path / "fetched_source").resolve()
    mock_fetcher_class.assert_called_once_with(
        base_save_path=str(fetcher_storage_base),
        package_info_dict=package_info_for_fetcher
    )
    mock_fetcher_instance.fetch.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
def test_internal_fetch_repo_fetch_failure(mock_fetcher_class, mock_orchestrator, tmp_path):
    mock_fetcher_instance = mock_fetcher_class.return_value
    mock_fetcher_instance.fetch.return_value = (False, False, None)

    fetcher_storage_base = tmp_path / "_fetched_project_sources"
    package_info_for_fetcher = {"name": "test_package", "version": "1.0.0", "project_urls": {}}

    result = mock_orchestrator._fetch_repo_fetch(fetcher_storage_base, package_info_for_fetcher)

    assert result is None
    mock_fetcher_class.assert_called_once()
    mock_fetcher_instance.fetch.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
def test_internal_fetch_repo_fetch_raises_os_error(mock_fetcher_class, mock_orchestrator, tmp_path):
    mock_fetcher_instance = mock_fetcher_class.return_value
    mock_fetcher_instance.fetch.side_effect = OSError("Disk full")

    fetcher_storage_base = tmp_path / "_fetched_project_sources"
    package_info_for_fetcher = {"name": "test_package", "version": "1.0.0", "project_urls": {}}

    result = mock_orchestrator._fetch_repo_fetch(fetcher_storage_base, package_info_for_fetcher)

    assert result is None
    mock_fetcher_class.assert_called_once()
    mock_fetcher_instance.fetch.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.PackageSourceFetcher')
def test_internal_fetch_repo_fetch_raises_runtime_error(mock_fetcher_class, mock_orchestrator, tmp_path):
    mock_fetcher_instance = mock_fetcher_class.return_value
    mock_fetcher_instance.fetch.side_effect = RuntimeError("Network error")

    fetcher_storage_base = tmp_path / "_fetched_project_sources"
    package_info_for_fetcher = {"name": "test_package", "version": "1.0.0", "project_urls": {}}

    result = mock_orchestrator._fetch_repo_fetch(fetcher_storage_base, package_info_for_fetcher)

    assert result is None
    mock_fetcher_class.assert_called_once()
    mock_fetcher_instance.fetch.assert_called_once()

# Tests for start_scan method
@patch('devildex.orchestrator.documentation_orchestrator.Orchestrator.fetch_repo')
def test_start_scan_fetch_repo_fails(mock_fetch_repo, mock_orchestrator):
    mock_fetch_repo.return_value = False
    mock_orchestrator.start_scan()
    assert mock_orchestrator.detected_doc_type == "unknown"
    mock_fetch_repo.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.Orchestrator.fetch_repo', return_value=True)
@patch('devildex.orchestrator.documentation_orchestrator.is_sphinx_project', return_value=True)
@patch('devildex.orchestrator.documentation_orchestrator.is_mkdocs_project', return_value=False)
@patch('devildex.orchestrator.documentation_orchestrator.has_docstrings', return_value=False)
def test_start_scan_detects_sphinx(mock_has_docstrings, mock_is_mkdocs_project, mock_is_sphinx_project, mock_fetch_repo, mock_orchestrator, tmp_path):
    mock_orchestrator._effective_source_path = tmp_path / "source"
    mock_orchestrator.start_scan()
    assert mock_orchestrator.detected_doc_type == "sphinx"
    mock_is_sphinx_project.assert_called_once_with(str(tmp_path / "source"))
    mock_is_mkdocs_project.assert_not_called()
    mock_has_docstrings.assert_not_called()

@patch('devildex.orchestrator.documentation_orchestrator.Orchestrator.fetch_repo', return_value=True)
@patch('devildex.orchestrator.documentation_orchestrator.is_sphinx_project', return_value=False)
@patch('devildex.orchestrator.documentation_orchestrator.is_mkdocs_project', return_value=True)
@patch('devildex.orchestrator.documentation_orchestrator.has_docstrings', return_value=False)
def test_start_scan_detects_mkdocs(mock_has_docstrings, mock_is_mkdocs_project, mock_is_sphinx_project, mock_fetch_repo, mock_orchestrator, tmp_path):
    mock_orchestrator._effective_source_path = tmp_path / "source"
    mock_orchestrator.start_scan()
    assert mock_orchestrator.detected_doc_type == "mkdocs"
    mock_is_sphinx_project.assert_called_once()
    mock_is_mkdocs_project.assert_called_once_with(str(tmp_path / "source"))
    mock_has_docstrings.assert_not_called()

@patch('devildex.orchestrator.documentation_orchestrator.Orchestrator.fetch_repo', return_value=True)
@patch('devildex.orchestrator.documentation_orchestrator.is_sphinx_project', return_value=False)
@patch('devildex.orchestrator.documentation_orchestrator.is_mkdocs_project', return_value=False)
@patch('devildex.orchestrator.documentation_orchestrator.has_docstrings', return_value=True)
def test_start_scan_detects_docstrings(mock_has_docstrings, mock_is_mkdocs_project, mock_is_sphinx_project, mock_fetch_repo, mock_orchestrator, tmp_path):
    mock_orchestrator._effective_source_path = tmp_path / "source"
    mock_orchestrator.start_scan()
    assert mock_orchestrator.detected_doc_type == "docstrings"
    mock_is_sphinx_project.assert_called_once()
    mock_is_mkdocs_project.assert_called_once()
    mock_has_docstrings.assert_called_once_with(str(tmp_path / "source"))

@patch('devildex.orchestrator.documentation_orchestrator.Orchestrator.fetch_repo', return_value=True)
@patch('devildex.orchestrator.documentation_orchestrator.is_sphinx_project', return_value=False)
@patch('devildex.orchestrator.documentation_orchestrator.is_mkdocs_project', return_value=False)
@patch('devildex.orchestrator.documentation_orchestrator.has_docstrings', return_value=False)
def test_start_scan_detects_unknown(mock_has_docstrings, mock_is_mkdocs_project, mock_is_sphinx_project, mock_fetch_repo, mock_orchestrator, tmp_path):
    mock_orchestrator._effective_source_path = tmp_path / "source"
    mock_orchestrator.start_scan()
    assert mock_orchestrator.detected_doc_type == "unknown"
    mock_is_sphinx_project.assert_called_once()
    mock_is_mkdocs_project.assert_called_once()
    mock_has_docstrings.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.Orchestrator.fetch_repo', return_value=True)
@patch('devildex.orchestrator.documentation_orchestrator.is_sphinx_project', return_value=False)
@patch('devildex.orchestrator.documentation_orchestrator.is_mkdocs_project', return_value=False)
@patch('devildex.orchestrator.documentation_orchestrator.has_docstrings', return_value=False)
def test_start_scan_effective_source_path_none(mock_has_docstrings, mock_is_mkdocs_project, mock_is_sphinx_project, mock_fetch_repo, mock_orchestrator):
    mock_orchestrator._effective_source_path = None # Simulate fetch_repo returning True but _effective_source_path somehow being None
    mock_orchestrator.start_scan()
    assert mock_orchestrator.detected_doc_type == "unknown"
    mock_is_sphinx_project.assert_not_called()
    mock_is_mkdocs_project.assert_not_called()
    mock_has_docstrings.assert_not_called()

# Tests for grab_build_doc method
def test_grab_build_doc_no_scan_result(mock_orchestrator):
    mock_orchestrator.detected_doc_type = None
    result = mock_orchestrator.grab_build_doc()
    assert result is False
    assert mock_orchestrator.last_operation_result is False

def test_grab_build_doc_unknown_doc_type(mock_orchestrator):
    mock_orchestrator.detected_doc_type = "unknown"
    result = mock_orchestrator.grab_build_doc()
    assert result is False
    assert mock_orchestrator.last_operation_result is False

@patch('devildex.orchestrator.documentation_orchestrator.download_readthedocs_source_and_build')
def test_grab_build_doc_sphinx(mock_download_sphinx, mock_orchestrator, tmp_path):
    mock_orchestrator.detected_doc_type = "sphinx"
    mock_orchestrator._effective_source_path = tmp_path / "source"
    mock_download_sphinx.return_value = "sphinx_output_path"
    result = mock_orchestrator.grab_build_doc()
    assert result == "sphinx_output_path"
    assert mock_orchestrator.last_operation_result == "sphinx_output_path"
    mock_download_sphinx.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.download_readthedocs_source_and_build')
def test_grab_build_doc_sphinx_with_existing_source_path(mock_download_sphinx, mock_orchestrator, tmp_path):
    mock_orchestrator.detected_doc_type = "sphinx"
    existing_source_path = tmp_path / "existing_source"
    existing_source_path.mkdir()
    mock_orchestrator._effective_source_path = existing_source_path
    mock_download_sphinx.return_value = "sphinx_output_path"
    result = mock_orchestrator.grab_build_doc()
    assert result == "sphinx_output_path"
    assert mock_orchestrator.last_operation_result == "sphinx_output_path"
    mock_download_sphinx.assert_called_once_with(
        project_url=mock_orchestrator.package_details.vcs_url,
        project_name=mock_orchestrator.package_details.name,
        output_dir=mock_orchestrator.base_output_dir,
        clone_base_dir_override=mock_orchestrator.base_output_dir / "temp_clones",
        existing_clone_path=existing_source_path
    )

@patch('devildex.orchestrator.documentation_orchestrator.download_readthedocs_source_and_build')
def test_grab_build_doc_sphinx_raises_exception(mock_download_sphinx, mock_orchestrator, tmp_path):
    mock_orchestrator.detected_doc_type = "sphinx"
    mock_orchestrator._effective_source_path = tmp_path / "source"
    mock_download_sphinx.side_effect = Exception("Sphinx build failed")
    result = mock_orchestrator.grab_build_doc()
    assert result is False
    assert mock_orchestrator.last_operation_result is False
    mock_download_sphinx.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.process_mkdocs_source_and_build')
def test_grab_build_doc_mkdocs(mock_process_mkdocs, mock_orchestrator, tmp_path):
    mock_orchestrator.detected_doc_type = "mkdocs"
    mock_orchestrator._effective_source_path = tmp_path / "source"
    mock_process_mkdocs.return_value = "mkdocs_output_path"
    result = mock_orchestrator.grab_build_doc()
    assert result == "mkdocs_output_path"
    assert mock_orchestrator.last_operation_result == "mkdocs_output_path"
    mock_process_mkdocs.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.download_readthedocs_prebuilt_robust')
def test_grab_build_doc_readthedocs(mock_download_readthedocs, mock_orchestrator):
    mock_orchestrator.detected_doc_type = "readthedocs"
    mock_download_readthedocs.return_value = "readthedocs_output_path"
    result = mock_orchestrator.grab_build_doc()
    assert result == "readthedocs_output_path"
    assert mock_orchestrator.last_operation_result == "readthedocs_output_path"
    mock_download_readthedocs.assert_called_once()

@patch('devildex.orchestrator.documentation_orchestrator.DocStringsSrc.generate_docs_from_folder')
def test_grab_build_doc_docstrings(mock_generate_docs_from_folder, mock_orchestrator, tmp_path):
    mock_orchestrator.detected_doc_type = "docstrings"
    mock_orchestrator._effective_source_path = tmp_path / "source"
    mock_generate_docs_from_folder.return_value = "docstrings_output_path"
    result = mock_orchestrator.grab_build_doc()
    assert result == "docstrings_output_path"
    assert mock_orchestrator.last_operation_result == "docstrings_output_path"
    mock_generate_docs_from_folder.assert_called_once()

def test_grab_build_doc_key_error(mock_orchestrator):
    mock_orchestrator.detected_doc_type = "non_existent_type"
    result = mock_orchestrator.grab_build_doc()
    assert result is False
    assert mock_orchestrator.last_operation_result is False

def test_interpret_tuple_res_string():
    result = Orchestrator._interpret_tuple_res("some_string")
    assert result == "some_string"

def test_interpret_tuple_res_tuple_true():
    result = Orchestrator._interpret_tuple_res(("path/to/doc", True))
    assert result == "path/to/doc"

def test_interpret_tuple_res_tuple_false():
    result = Orchestrator._interpret_tuple_res(("path/to/doc", False))
    assert result is False

def test_get_detected_doc_type(mock_orchestrator):
    mock_orchestrator.detected_doc_type = "sphinx"
    assert mock_orchestrator.get_detected_doc_type() == "sphinx"

def test_get_last_operation_result(mock_orchestrator):
    mock_orchestrator.last_operation_result = "success"
    assert mock_orchestrator.get_last_operation_result() == "success"