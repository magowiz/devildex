"""generate_pyproject_toml module."""

import logging
import re
import sys
from collections import OrderedDict

import toml

logger = logging.getLogger(__name__)


def parse_dependency_string(dep_string: str) -> tuple[str, str]:
    """Parse a dependency string into package name and version constraint.

    Parses a dependency string like 'package (>=version,<version)' into
    (package_name, version_constraint).
    """
    match = re.match(r"^([a-zA-Z0-9_.-]+)(?:\s*\((.*)\))?$", dep_string)
    if match:
        name = match.group(1)
        constraint = match.group(2) if match.group(2) else "*"
        return name, constraint
    return dep_string, "*"  # Fallback if parsing fails


def _handle_poetry_metadata(project_data: dict, tool_poetry_data: OrderedDict) -> None:
    """Handle project metadata conversion for Poetry."""
    for key in [
        "name",
        "version",
        "description",
        "license",
        "readme",
        "homepage",
        "repository",
        "documentation",
        "keywords",
        "classifiers",
    ]:
        if key in project_data:
            tool_poetry_data[key] = project_data[key]

    if "authors" in project_data:
        tool_poetry_data["authors"] = [
            f"{author['name']} <{author['email']}>"
            for author in project_data["authors"]
        ]


def _handle_poetry_dependencies(
    project_data: dict, tool_poetry_data: OrderedDict
) -> None:
    """Handle project dependencies conversion for Poetry."""
    if "requires-python" in project_data:
        tool_poetry_data["dependencies"] = {"python": project_data["requires-python"]}

    if "dependencies" in project_data:
        converted_deps = OrderedDict()
        for dep_string in project_data["dependencies"]:
            name, constraint = parse_dependency_string(dep_string)
            converted_deps[name] = constraint
        tool_poetry_data["dependencies"] = {
            **tool_poetry_data.get("dependencies", {}),
            **converted_deps,
        }


def _handle_poetry_extras_and_scripts(
    project_data: dict, tool_poetry_data: OrderedDict
) -> None:
    """Handle optional dependencies and scripts conversion for Poetry."""
    if "optional-dependencies" in project_data:
        tool_poetry_data["extras"] = project_data["optional-dependencies"]

    if "scripts" in project_data:
        tool_poetry_data["scripts"] = project_data["scripts"]


def _handle_poetry_build_system(data: dict) -> None:
    """Handle build-system conversion for Poetry."""
    if (
        "build-system" in data
        and "requires" in data["build-system"]
        and any("poetry-core" in req for req in data["build-system"]["requires"])
    ):
        data.pop("build-system")


def convert_to_poetry_1x(data: dict) -> dict:
    """Convert a pyproject.toml from PEP 621 format to Poetry 1.x format."""
    if "project" not in data:
        return data

    project_data = data["project"]
    tool_poetry_data = OrderedDict()

    _handle_poetry_metadata(project_data, tool_poetry_data)
    _handle_poetry_dependencies(project_data, tool_poetry_data)
    _handle_poetry_extras_and_scripts(project_data, tool_poetry_data)
    _handle_poetry_build_system(data)

    # Construct new data structure
    new_data = OrderedDict()
    new_data["tool"] = {"poetry": tool_poetry_data}
    if "build-system" in data:
        new_data["build-system"] = data["build-system"]

    return new_data


def generate_pyproject_toml(original_path: str, tgt_os: str) -> str:
    """Generate a pyproject.toml file with platform-specific adjustments.

    Args:
        original_path: Path to the original pyproject.toml file.
        tgt_os: Target operating system (e.g., 'windows', 'macos', 'linux', 'fedora').

    Returns:
        The modified pyproject.toml content as a string.

    """
    with open(original_path) as f:
        data = toml.load(f)

    # Apply platform-specific dependency filtering
    if tgt_os.lower() in ["windows", "macos", "fedora"]:
        # Check both project.dependencies and tool.poetry.dependencies
        if "project" in data and "dependencies" in data["project"]:
            dependencies = data["project"]["dependencies"]
            new_dependencies = []
            for dep in dependencies:
                if "wxpython" not in dep or "linux_x86_64.whl" not in dep:
                    new_dependencies.append(dep)
            data["project"]["dependencies"] = new_dependencies
        elif (
            "tool" in data
            and "poetry" in data["tool"]
            and "dependencies" in data["tool"]["poetry"]
        ):
            dependencies = data["tool"]["poetry"]["dependencies"]
            new_dependencies = []
            for dep in dependencies:
                if "wxpython" not in dep or "linux_x86_64.whl" not in dep:
                    new_dependencies.append(dep)
            data["tool"]["poetry"]["dependencies"] = new_dependencies

    # Apply Poetry 2.x to 1.x conversion for specific OS
    if tgt_os.lower() in ["fedora", "windows", "macos"]:
        data = convert_to_poetry_1x(data)

    return toml.dumps(data)


if __name__ == "__main__":
    original_pyproject_toml_path = sys.argv[1]
    target_os = sys.argv[2]  # 'windows', 'macos', 'linux', or 'fedora'
    logger.info(target_os)

    modified_content = generate_pyproject_toml(original_pyproject_toml_path, target_os)
    sys.stdout.write(modified_content)
