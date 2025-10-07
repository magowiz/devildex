"""Convert pyproject.toml from PEP 621 to Poetry 1.x format.

This script provides functionality to convert a `pyproject.toml` file
from the PEP 621 metadata format to the Poetry 1.x specific format.
It is particularly useful for projects that need to maintain compatibility
with older Poetry versions while adopting the newer PEP 621 standard.
"""
import logging
import re
import sys
from collections import OrderedDict
from typing import Any, Optional

import toml

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Constant for magic value
PARTS_LENGTH_TWO = 2
EXPECTED_ARG_COUNT = 3 # New constant for magic value

def parse_dependency_string(dep_string: str) -> tuple[Optional[str], Optional[Any]]:
    """Parse a dependency string into package name and version/URL specifier.

    Args:
        dep_string: The dependency string to parse.

    Returns:
        A tuple containing the package name and its version/URL specifier,
        or (None, None) if parsing fails.

    """
    # Handle URL dependencies first
    match_url = re.match(r'([^ ]+) @ (.*)', dep_string)
    if match_url:
        package_name = match_url.group(1).strip()
        url = match_url.group(2).strip()
        return package_name, {'url': url}

    # Handle version specifiers in parentheses
    match_version_spec = re.match(r'([^ ]+) \((.*)\)', dep_string)
    if match_version_spec:
        package_name = match_version_spec.group(1).strip()
        version_spec = match_version_spec.group(2).strip()
        return package_name, version_spec

    # Handle simple package name with optional version
    # (e.g., "package ^1.0.0" or "package")
    parts = dep_string.split(' ', 1)  # Split only at the first space
    if len(parts) == PARTS_LENGTH_TWO:
        package_name = parts[0].strip()
        version_spec = parts[1].strip()
        return package_name, version_spec
    elif len(parts) == 1:
        package_name = parts[0].strip()
        return package_name, "*"  # Default to any version if not specified

    logging.warning(
        f"Could not fully parse dependency string '{dep_string}'. Skipping."
    )
    return None, None

def _handle_project_metadata(project: dict, new_data: OrderedDict) -> None:
    """Handle project metadata conversion."""
    new_data['tool']['poetry']['name'] = project.get('name')
    new_data['tool']['poetry']['version'] = project.get('version')
    new_data['tool']['poetry']['description'] = project.get('description')

    # Convert authors format
    authors = project.get('authors', [])
    formatted_authors = []
    for author in authors:
        name = author.get('name')
        email = author.get('email')
        if name and email:
            formatted_authors.append(f"{name} <{email}>")
        elif name:
            formatted_authors.append(name)
    if formatted_authors:
        new_data['tool']['poetry']['authors'] = formatted_authors

    new_data['tool']['poetry']['readme'] = project.get('readme')

def _handle_project_packages(data: dict, new_data: OrderedDict) -> None:
    """Handle project packages conversion."""
    if (
        'tool' in data and 'poetry' in data['tool'] and
        'packages' in data['tool']['poetry']
    ):
        new_data['tool']['poetry']['packages'] = data['tool']['poetry']['packages']

def _handle_project_dependencies(project: dict, new_data: OrderedDict) -> None:
    """Handle project dependencies conversion."""
    new_data['tool']['poetry']['dependencies'] = OrderedDict()
    if 'requires-python' in project:
        new_data['tool']['poetry']['dependencies']['python'] = \
            project['requires-python'] # Line break for E501

    if 'dependencies' in project:
        for dep_string in project['dependencies']:
            package_name, dep_spec = parse_dependency_string(dep_string)
            if package_name and dep_spec:
                new_data['tool']['poetry']['dependencies'][package_name] = dep_spec

def _handle_project_scripts(data: dict, new_data: OrderedDict) -> None:
    """Handle project scripts conversion."""
    if 'project' in data and 'scripts' in data['project']:
        new_data['tool']['poetry']['scripts'] = data['project']['scripts']

def _handle_dev_dependencies(data: dict, new_data: OrderedDict) -> None:
    """Handle development dependencies conversion."""
    new_data['tool']['poetry']['dev-dependencies'] = OrderedDict()
    if (
        'tool' in data and 'poetry' in data['tool'] and
        'group' in data['tool']['poetry']
    ):
        for _group_name, group_data in data['tool']['poetry']['group'].items():
            if 'dependencies' in group_data:
                for dep_name, dep_spec in group_data['dependencies'].items():
                    new_data['tool']['poetry']['dev-dependencies'][dep_name] = dep_spec

def _process_project_data(data: dict, new_data: OrderedDict) -> None:
    """Process project data and populate new_data."""
    if 'project' in data:
        project = data['project']
        _handle_project_metadata(project, new_data)
        _handle_project_packages(data, new_data)
        _handle_project_dependencies(project, new_data)

    _handle_project_scripts(data, new_data)
    _handle_dev_dependencies(data, new_data)

def _initialize_new_data() -> OrderedDict:
    """Initialize the new_data OrderedDict structure."""
    new_data = OrderedDict()
    new_data['tool'] = OrderedDict()
    new_data['tool']['poetry'] = OrderedDict()
    return new_data

def _read_toml_file(input_file: str) -> dict:
    """Read and parse a TOML file."""
    try:
        with open(input_file) as f:
            data = toml.load(f)
    except FileNotFoundError:
        logging.exception(f"Input file '{input_file}' not found.")
        sys.exit(1)
    except toml.TomlDecodeError:
        logging.exception(f"Error decoding TOML from '{input_file}'.")
        sys.exit(1)
    else:
        return data

def convert_pyproject_to_poetry_1x(input_file: str, output_file: str) -> None:
    """Convert a pyproject.toml from PEP 621 format to Poetry 1.x format.

    Args:
        input_file: Path to the input pyproject.toml file (PEP 621 format).
        output_file: Path to the output pyproject.toml file (Poetry 1.x format).

    """
    data = _read_toml_file(input_file) # Call new helper function
    new_data = _initialize_new_data()

    _process_project_data(data, new_data)

    # Add build-system back
    if 'build-system' in data:
        new_data['build-system'] = data['build-system']

    try:
        with open(output_file, 'w') as f:
            toml.dump(new_data, f)
        logging.info(
            f"Successfully converted '{input_file}' to Poetry 1.x format in "
            f"'{output_file}'."
        )
    except OSError:
        logging.exception(f"Error writing output file '{output_file}'.")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != EXPECTED_ARG_COUNT:
        logging.error(
            "Usage: python convert_poetry.py <input_pyproject.toml> "
            "<output_pyproject.toml>"
        )
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    convert_pyproject_to_poetry_1x(input_path, output_path)
