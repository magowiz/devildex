import logging
import sys
from pathlib import Path

import toml

logger = logging.getLogger(__name__)


def generate_pyproject_toml(original_path: Path, tgt_os: str):
    with open(original_path) as f:
        data = toml.load(f)

    if tgt_os in ["windows", "macos"]:
        dependencies = data["project"]["dependencies"]
        new_dependencies = []
        for dep in dependencies:
            if "wxpython" not in dep or "linux_x86_64.whl" not in dep:
                new_dependencies.append(dep)
        data["project"]["dependencies"] = new_dependencies
    return toml.dumps(data)


if __name__ == "__main__":
    original_pyproject_toml_path = sys.argv[1]
    target_os = sys.argv[2]  # 'windows', 'macos', or 'linux'
    logger.info(target_os)

    modified_content = generate_pyproject_toml(original_pyproject_toml_path, target_os)
    sys.stdout.write(modified_content)
