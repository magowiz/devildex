"""test mkdocs src module."""

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from devildex.mkdocs.mkdocs_src import (
    MkDocsBuildContext,
    _add_callouts_to_plugins_if_missing,
    _execute_mkdocs_build_in_venv,
    _extract_callouts_from_markdown_extensions,
    _extract_names_from_config_list_or_dict,
    _find_mkdocs_config_file,
    _get_plugin_packages_to_install,
    _get_theme_packages_to_install,
    _is_plugin_callouts,
    _parse_mkdocs_config,
    _prepare_mkdocs_output_directory,
    _preprocess_mkdocs_config,
    process_mkdocs_source_and_build,
)


def create_mkdocs_yml(path: Path, content: dict | None = None):
    if content is None:
        content = {"site_name": "Test Site"}
    path.mkdir(parents=True, exist_ok=True)
    (path / "mkdocs.yml").write_text(yaml.dump(content))


def test_find_mkdocs_config_file_at_root(tmp_path: Path):
    """Should find mkdocs.yml at the project root."""
    create_mkdocs_yml(tmp_path)
    assert _find_mkdocs_config_file(tmp_path) == tmp_path / "mkdocs.yml"


def test_find_mkdocs_config_file_in_docs_subdir(tmp_path: Path):
    """Should find mkdocs.yml in a 'docs' subdirectory."""
    docs_path = tmp_path / "docs"
    create_mkdocs_yml(docs_path)
    assert _find_mkdocs_config_file(tmp_path) == docs_path / "mkdocs.yml"


def test_find_mkdocs_config_file_not_found(tmp_path: Path):
    """Should return None if mkdocs.yml is not found."""
    assert _find_mkdocs_config_file(tmp_path) is None


# --- Tests for _parse_mkdocs_config ---


def test_parse_mkdocs_config_valid_yaml(tmp_path: Path):
    """Should parse a valid mkdocs.yml file."""
    config_content = {"site_name": "My Test Site", "nav": ["index.md"]}
    create_mkdocs_yml(tmp_path, config_content)
    config_path = tmp_path / "mkdocs.yml"
    assert _parse_mkdocs_config(config_path) == config_content


def test_parse_mkdocs_config_invalid_yaml(tmp_path: Path):
    """Should return None for an invalid mkdocs.yml file."""
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text("site_name: [invalid yaml")  # Malformed YAML
    assert _parse_mkdocs_config(config_path) is None


def test_parse_mkdocs_config_file_not_found(tmp_path: Path):
    """Should return None if the config file does not exist."""
    config_path = tmp_path / "non_existent_mkdocs.yml"
    assert _parse_mkdocs_config(config_path) is None


# --- Tests for _extract_callouts_from_markdown_extensions ---


def test_extract_callouts_from_markdown_extensions_list_str(tmp_path: Path):
    """Should extract 'callouts' when it's a string in a list."""
    md_ext = ["admonition", "callouts", "footnotes"]
    updated, extracted, modified = _extract_callouts_from_markdown_extensions(md_ext)
    assert updated == ["admonition", "footnotes"]
    assert extracted == "callouts"
    assert modified is True


def test_extract_callouts_from_markdown_extensions_list_dict(tmp_path: Path):
    """Should extract 'callouts' when it's a dict in a list."""
    md_ext = ["admonition", {"callouts": {"data": "value"}}, "footnotes"]
    updated, extracted, modified = _extract_callouts_from_markdown_extensions(md_ext)
    assert updated == ["admonition", "footnotes"]
    assert extracted == {"callouts": {"data": "value"}}
    assert modified is True


def test_extract_callouts_from_markdown_extensions_dict(tmp_path: Path):
    """Should extract 'callouts' when it's a key in a dict."""
    md_ext = {"admonition": {}, "callouts": {"data": "value"}, "footnotes": {}}
    updated, extracted, modified = _extract_callouts_from_markdown_extensions(md_ext)
    assert updated == {"admonition": {}, "footnotes": {}}
    assert extracted == {"callouts": {"data": "value"}}
    assert modified is True


def test_extract_callouts_from_markdown_extensions_not_present(tmp_path: Path):
    """Should not modify if 'callouts' is not present."""
    md_ext = ["admonition", "footnotes"]
    updated, extracted, modified = _extract_callouts_from_markdown_extensions(md_ext)
    assert updated == md_ext
    assert extracted is None
    assert modified is False


def test_extract_callouts_from_markdown_extensions_empty_or_none(tmp_path: Path):
    """Should handle empty list, dict, or None gracefully."""
    assert _extract_callouts_from_markdown_extensions(None) == (None, None, False)
    assert _extract_callouts_from_markdown_extensions([]) == ([], None, False)
    assert _extract_callouts_from_markdown_extensions({}) == ({}, None, False)


# --- Tests for _is_plugin_callouts ---


def test_is_plugin_callouts_str():
    """Should return True for 'callouts' string."""
    assert _is_plugin_callouts("callouts") is True


def test_is_plugin_callouts_dict():
    """Should return True for {'callouts': ...} dict."""
    assert _is_plugin_callouts({"callouts": {"data": "value"}}) is True


def test_is_plugin_callouts_other_str():
    """Should return False for other strings."""
    assert _is_plugin_callouts("other_plugin") is False


def test_is_plugin_callouts_other_dict():
    """Should return False for other dicts."""
    assert _is_plugin_callouts({"other_plugin": {}}) is False


# --- Tests for _add_callouts_to_plugins_if_missing ---


def test_add_callouts_to_plugins_if_missing_empty_list():
    """Should add callouts to an empty plugin list."""
    plugins = []
    updated, added = _add_callouts_to_plugins_if_missing(plugins, "callouts")
    assert updated == ["callouts"]
    assert added is True


def test_add_callouts_to_plugins_if_missing_not_present():
    """Should add callouts if not already present."""
    plugins = ["search", "macros"]
    updated, added = _add_callouts_to_plugins_if_missing(plugins, {"callouts": {}})
    assert updated == ["search", "macros", {"callouts": {}}]
    assert added is True


def test_add_callouts_to_plugins_if_missing_already_present_str():
    """Should not add if callouts (str) is already present."""
    plugins = ["search", "callouts"]
    updated, added = _add_callouts_to_plugins_if_missing(plugins, "callouts")
    assert updated == ["search", "callouts"]
    assert added is False


def test_add_callouts_to_plugins_if_missing_already_present_dict() -> None:
    """Should not add if callouts (dict) is already present."""
    plugins = ["search", {"callouts": {}}]
    updated, added = _add_callouts_to_plugins_if_missing(plugins, {"callouts": {}})
    assert updated == ["search", {"callouts": {}}]
    assert added is False


def test_add_callouts_to_plugins_if_missing_none_config():
    """Should handle None as initial plugins config."""
    updated, added = _add_callouts_to_plugins_if_missing(None, "callouts")
    assert updated == ["callouts"]
    assert added is True


def test_add_callouts_to_plugins_if_missing_non_list_config():
    """Should handle non-list initial plugins config by initializing a new list."""
    updated, added = _add_callouts_to_plugins_if_missing("invalid_type", "callouts")
    assert updated == ["callouts"]
    assert added is True


# --- Tests for _preprocess_mkdocs_config ---


def test_preprocess_mkdocs_config_moves_callouts(tmp_path: Path):
    """Should move 'callouts' from markdown_extensions to plugins."""
    original_config = {
        "site_name": "Test",
        "markdown_extensions": ["admonition", "callouts"],
        "plugins": ["search"],
    }
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text(yaml.dump(original_config))

    processed_config, modified = _preprocess_mkdocs_config(original_config, config_path)

    assert modified is True
    assert "callouts" not in processed_config["markdown_extensions"]
    assert "callouts" in processed_config["plugins"]


def test_preprocess_mkdocs_config_resolves_docs_dir(tmp_path: Path):
    """Should resolve relative docs_dir to an absolute path."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").touch()

    original_config = {"site_name": "Test", "docs_dir": "docs"}
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text(yaml.dump(original_config))

    processed_config, modified = _preprocess_mkdocs_config(original_config, config_path)

    assert modified is True
    assert Path(processed_config["docs_dir"]).is_absolute()
    assert Path(processed_config["docs_dir"]) == docs_dir.resolve()


def test_preprocess_mkdocs_config_handles_none_config(tmp_path: Path):
    """Should return None and False if original_config_content is None."""
    config_path = tmp_path / "mkdocs.yml"
    processed_config, modified = _preprocess_mkdocs_config(None, config_path)
    assert processed_config is None
    assert modified is False


def test_preprocess_mkdocs_config_docs_dir_not_found(tmp_path: Path):
    """Should not resolve docs_dir if the directory does not exist."""
    original_config = {"site_name": "Test", "docs_dir": "non_existent_docs"}
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text(yaml.dump(original_config))

    processed_config, modified = _preprocess_mkdocs_config(original_config, config_path)

    assert modified is False  # No change because dir not found
    assert processed_config["docs_dir"] == "non_existent_docs"


# --- Tests for _get_theme_packages_to_install ---


def test_get_theme_packages_to_install_material():
    """Should return 'mkdocs-material' for 'material' theme."""
    assert _get_theme_packages_to_install("material") == ["mkdocs-material"]


def test_get_theme_packages_to_install_material_dict():
    """Should return 'mkdocs-material' for 'material' theme in dict form."""
    assert _get_theme_packages_to_install({"name": "material"}) == ["mkdocs-material"]


def test_get_theme_packages_to_install_mkdocs_or_readthedocs():
    """Should return empty list for 'mkdocs' or 'readthedocs' themes."""
    assert _get_theme_packages_to_install("mkdocs") == []
    assert _get_theme_packages_to_install("readthedocs") == []


def test_get_theme_packages_to_install_unknown_theme():
    """Should return empty list for unknown themes."""
    assert _get_theme_packages_to_install("unknown_theme") == []
    assert _get_theme_packages_to_install({"name": "unknown_theme"}) == []


def test_get_theme_packages_to_install_none():
    """Should return empty list for None theme config."""
    assert _get_theme_packages_to_install(None) == []


# --- Tests for _prepare_mkdocs_output_directory ---


def test_prepare_mkdocs_output_directory_creates_new(tmp_path: Path):
    """Should create the output directory if it doesn't exist."""
    base_output = tmp_path / "builds"
    output_dir = _prepare_mkdocs_output_directory(base_output, "my-project", "1.0")
    expected_dir = base_output / "mkdocs_builds" / "my-project" / "1.0"
    assert output_dir == expected_dir.resolve()
    assert output_dir.is_dir()


def test_prepare_mkdocs_output_directory_cleans_existing(tmp_path: Path):
    """Should clean (remove and recreate) an existing output directory."""
    base_output = tmp_path / "builds"
    existing_dir = base_output / "mkdocs_builds" / "my-project" / "1.0"
    existing_dir.mkdir(parents=True)
    (existing_dir / "old_file.txt").touch()

    output_dir = _prepare_mkdocs_output_directory(base_output, "my-project", "1.0")
    assert output_dir == existing_dir.resolve()
    assert output_dir.is_dir()
    assert not (output_dir / "old_file.txt").exists()  # Should be cleaned


def test_prepare_mkdocs_output_directory_os_error(tmp_path: Path, mocker: MagicMock):
    """Should return None if an OSError occurs during directory creation/cleaning."""
    # Mock Path.mkdir to raise an OSError
    mocker.patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied"))
    base_output = tmp_path / "builds"
    output_dir = _prepare_mkdocs_output_directory(base_output, "my-project", "1.0")
    assert output_dir is None


# --- Tests for _extract_names_from_config_list_or_dict ---


def test_extract_names_from_config_list_of_strings():
    """Should extract names from a list of strings."""
    config = ["plugin1", "plugin2"]
    assert _extract_names_from_config_list_or_dict(config) == ["plugin1", "plugin2"]


def test_extract_names_from_config_list_of_dicts() -> None:
    """Should extract names from a list of dictionaries."""
    config = [{"plugin1": {"opt": "val"}}, {"plugin2": {}}]
    assert _extract_names_from_config_list_or_dict(config) == ["plugin1", "plugin2"]


def test_extract_names_from_config_list_mixed():
    """Should extract names from a mixed list of strings and dictionaries."""
    config = ["plugin1", {"plugin2": {}}, "plugin3"]
    assert _extract_names_from_config_list_or_dict(config) == [
        "plugin1",
        "plugin2",
        "plugin3",
    ]


def test_extract_names_from_config_dict():
    """Should extract names from a dictionary."""
    config = {"plugin1": {}, "plugin2": {"opt": "val"}}
    assert _extract_names_from_config_list_or_dict(config) == ["plugin1", "plugin2"]


def test_extract_names_from_config_empty_or_none():
    """Should return empty list for empty or None config."""
    assert _extract_names_from_config_list_or_dict(None) == []
    assert _extract_names_from_config_list_or_dict([]) == []
    assert _extract_names_from_config_list_or_dict({}) == []


def test_extract_names_from_config_pymdownx_plugins():
    """Should handle pymdownx plugins correctly."""
    config = ["pymdownx.highlight", {"pymdownx.superfences": {}}]
    assert _extract_names_from_config_list_or_dict(config) == [
        "pymdownx.highlight",
        "pymdownx.superfences",
    ]


# --- Tests for _get_plugin_packages_to_install ---


def test_get_plugin_packages_to_install_basic():
    """Should identify basic plugin packages."""
    plugins = ["mkdocstrings", "macros"]
    markdown_extensions = []
    expected = sorted(set(["mkdocstrings[python]", "mkdocs-macros-plugin"]))
    assert (
        sorted(_get_plugin_packages_to_install(plugins, markdown_extensions))
        == expected
    )


def test_get_plugin_packages_to_install_pymdownx():
    """Should identify pymdownx packages."""
    plugins = []
    markdown_extensions = ["pymdownx.highlight", "pymdownx.superfences"]
    expected = sorted(set(["pymdown-extensions"]))
    assert (
        sorted(_get_plugin_packages_to_install(plugins, markdown_extensions))
        == expected
    )


def test_get_plugin_packages_to_install_built_in():
    """Should ignore built-in plugins/extensions."""
    plugins = ["search"]
    markdown_extensions = ["toc"]
    assert _get_plugin_packages_to_install(plugins, markdown_extensions) == []


def test_get_plugin_packages_to_install_mixed():
    """Should handle a mix of known, unknown, and built-in."""
    plugins = ["mkdocstrings", {"search": {}}]
    markdown_extensions = ["pymdownx.highlight", "admonition", "unknown_ext"]
    expected = sorted(set(["mkdocstrings[python]", "pymdown-extensions"]))
    actual = _get_plugin_packages_to_install(plugins, markdown_extensions)
    assert sorted(actual) == expected


def test_get_plugin_packages_to_install_none_configs():
    """Should return empty list if both configs are None."""
    assert _get_plugin_packages_to_install(None, None) == []


def test_execute_mkdocs_build_in_venv_integration_success(tmp_path: Path) -> None:
    """Should successfully execute mkdocs build within a venv."""
    # Use a fixed output directory for easier debugging
    fixed_output_dir = tmp_path / "mkdocs_test_output"
    fixed_output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Setup dummy mkdocs project
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    docs_dir = project_root / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello MkDocs")

    mkdocs_config_content = {
        "site_name": "Test Integration Site",
        "docs_dir": str(docs_dir.relative_to(project_root)),
        "plugins": ["search"],
        "theme": "readthedocs",
    }
    (project_root / "mkdocs.yml").write_text(yaml.dump(mkdocs_config_content))

    # 2. Prepare build context
    build_ctx = MkDocsBuildContext(
        config_content=mkdocs_config_content,
        project_root=project_root,
        final_output_dir=fixed_output_dir,
        project_slug="test-integration-project",
        version_identifier="1.0",
        source_config_path=project_root / "mkdocs.yml",
    )

    # 3. Execute the real function
    # This will create a real isolated venv and run mkdocs build inside it.
    # It relies on mkdocs and its dependencies being installable via pip.
    success = _execute_mkdocs_build_in_venv(build_ctx)

    # 4. Assertions
    assert success is True
    assert fixed_output_dir.is_dir()
    assert (fixed_output_dir / "index.html").is_file()
    assert (
        fixed_output_dir / "404.html"
    ).is_file()  # Readthedocs theme usually generates this
    assert any(
        (fixed_output_dir / "js").glob("*.js")
    )  # Check for any JS file in the js directory


def test_process_mkdocs_source_and_build_integration_success(tmp_path: Path) -> None:
    """Should successfully process and build a dummy mkdocs project."""
    source_project_path = tmp_path / "source_project"
    source_project_path.mkdir()
    docs_dir = source_project_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello from Process Build")

    mkdocs_config_content = {
        "site_name": "Process Build Test Site",
        "docs_dir": str(docs_dir.relative_to(source_project_path)),
        "theme": "readthedocs",
    }
    (source_project_path / "mkdocs.yml").write_text(yaml.dump(mkdocs_config_content))

    base_output_dir = tmp_path / "base_output"
    project_slug = "test-process-build"
    version_identifier = "1.0"

    output_path = process_mkdocs_source_and_build(
        source_project_path=str(source_project_path),
        project_slug=project_slug,
        version_identifier=version_identifier,
        base_output_dir=base_output_dir,
    )

    assert output_path is not None
    output_dir = Path(output_path)
    assert output_dir.is_dir()
    assert (output_dir / "index.html").is_file()
    assert (
        output_dir / "404.html"
    ).is_file()  # Readthedocs theme usually generates this
    assert any(
        (output_dir / "js").glob("*.js")
    )  # Check for any JS file in the js directory
