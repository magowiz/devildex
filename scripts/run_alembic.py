"""run alembic."""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def main() -> None:
    """Run alembic command with the correct config path."""
    project_root = Path(__file__).resolve().parent.parent
    alembic_ini_path = project_root / "src" / "devildex" / "alembic.ini"
    command = [
        "alembic",
        "-c",
        str(alembic_ini_path),
    ]
    command.extend(sys.argv[1:])
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        logger.exception(
            "Error: 'alembic' command not found. Is alembic installed "
            "in your environment?"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
