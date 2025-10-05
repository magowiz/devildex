import logging
import sys
import re

import toml

logger = logging.getLogger(__name__)


def parse_dependency_string(dep_string: str) -> tuple[str, str]:
    """Parses a dependency string like 'package (>=version,<version)' into (package_name, version_constraint)."""
    match = re.match(r"^([a-zA-Z0-9_.-]+)(?:\s*\((.*)\))?$", dep_string)
    if match:
        name = match.group(1)
        constraint = match.group(2) if match.group(2) else "*"
        return name, constraint
    return dep_string, "*" # Fallback if parsing fails


def convert_to_poetry_1x(data: dict) -> dict:
    """Converts a pyproject.toml from PEP 621 format to Poetry 1.x format."""
    if "project" not in data:
        return data

    project_data = data.pop("project")
    tool_poetry_data = data.setdefault("tool", {}).setdefault("poetry", {})

    # Move core metadata
    for key in ["name", "version", "description", "license", "readme", "homepage", "repository", "documentation", "keywords", "classifiers"]:
        if key in project_data:
            tool_poetry_data[key] = project_data[key]

    # Handle authors: convert list of dicts to list of strings
    if "authors" in project_data:
        tool_poetry_data["authors"] = [f"{author['name']} <{author['email']}>" for author in project_data["authors"]]

    # Handle requires-python
    if "requires-python" in project_data:
        tool_poetry_data["dependencies"] = tool_poetry_data.get("dependencies", {})
        tool_poetry_data["dependencies"]["python"] = project_data["requires-python"]

    # Handle dependencies: convert list to dict
    if "dependencies" in project_data:
        converted_deps = {}
        for dep_string in project_data["dependencies"]:
            name, constraint = parse_dependency_string(dep_string)
            converted_deps[name] = constraint
        tool_poetry_data["dependencies"] = {**tool_poetry_data.get("dependencies", {}), **converted_deps}

    # Handle optional-dependencies to extras
    if "optional-dependencies" in project_data:
        tool_poetry_data["extras"] = {}
        for group_name, deps_list in project_data["optional-dependencies"].items():
            converted_extra_deps = {}
            for dep_string in deps_list:
                name, constraint = parse_dependency_string(dep_string)
                converted_extra_deps[name] = constraint
            tool_poetry_data["extras"][group_name] = converted_extra_deps

    # Handle scripts
    if "scripts" in project_data:
        tool_poetry_data["scripts"] = project_data["scripts"]

    # Handle build-system (remove if it's poetry-core based, as 1.x doesn't use it this way)
    if "build-system" in data:
        if "requires" in data["build-system"] and any("poetry-core" in req for req in data["build-system"]["requires"]):
            data.pop("build-system")

    return data


def generate_pyproject_toml(original_path: str, tgt_os: str):
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
        elif "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
            dependencies = data["tool"]["poetry"]["dependencies"]
            new_dependencies = []
            for dep in dependencies:
                if "wxpython" not in dep or "linux_x86_64.whl" not in dep:
                    new_dependencies.append(dep)
            data["tool"]["poetry"]["dependencies"] = new_dependencies

    # Apply Poetry 2.x to 1.x conversion for specific OS where old Poetry might be present
    if tgt_os.lower() in ["fedora", "windows", "macos"]:
        data = convert_to_poetry_1x(data)

    return toml.dumps(data)


if __name__ == "__main__":
    original_pyproject_toml_path = sys.argv[1]
    target_os = sys.argv[2]  # 'windows', 'macos', 'linux', or 'fedora'
    logger.info(target_os)

    modified_content = generate_pyproject_toml(original_pyproject_toml_path, target_os)
    sys.stdout.write(modified_content)