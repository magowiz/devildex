import toml
import sys

def generate_pyproject_toml(original_path, target_os):
    with open(original_path, 'r') as f:
        data = toml.load(f)

    if target_os in ['windows', 'macos']:
        dependencies = data['project']['dependencies']
        new_dependencies = []
        for dep in dependencies:
            if "wxpython" not in dep or "linux_x86_64.whl" not in dep:
                new_dependencies.append(dep)
        data['project']['dependencies'] = new_dependencies
    
    # For Linux, we keep the wxpython dependency as is.
    # No changes needed for Linux if the original pyproject.toml already has it.

    return toml.dumps(data)

if __name__ == "__main__":
    original_pyproject_toml_path = sys.argv[1]
    target_os = sys.argv[2] # 'windows', 'macos', or 'linux'

    modified_content = generate_pyproject_toml(original_pyproject_toml_path, target_os)
    sys.stdout.write(modified_content)
