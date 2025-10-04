import subprocess
import sys
from pathlib import Path

def main() -> None:
    """Run alembic command with the correct config path."""
    # Project root is the parent directory of the 'scripts' directory where this file lives
    project_root = Path(__file__).resolve().parent.parent

    # Path to the alembic.ini file inside the package
    alembic_ini_path = project_root / "src" / "devildex" / "alembic.ini"

    # The base command to run. 'poetry run' is not needed as this script
    # will be executed by poetry itself, inheriting the virtual environment.
    command = [
        "alembic",
        "-c",
        str(alembic_ini_path),
    ]

    # Append all command-line arguments passed to this script
    command.extend(sys.argv[1:])

    # Execute the command
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: 'alembic' command not found. Is alembic installed in your environment?")
        sys.exit(1)

if __name__ == "__main__":
    main()
