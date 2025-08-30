import importlib.metadata
import json
import logging
import sys
import traceback

PATHS_LEN = 2
logger = logging.getLogger(__name__)


def _args_checker() -> None:
    if len(sys.argv) < PATHS_LEN:
        logger.debug(
            "DEBUG_HELPER: Error: Output file path not provided as argument.",
        )
        sys.exit(2)


def _reconfigure_logs() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def _main_write_json(output_file_path: str, package_list: list[dict]) -> None:
    try:
        with open(output_file_path, "w", encoding="utf-8") as f_out:
            json.dump(package_list, f_out, indent=2)
        logger.debug(
            f"DEBUG_HELPER: Successfully wrote JSON to {output_file_path}",
        )
        sys.exit(0)
    except OSError as e_io:
        logger.debug(
            "DEBUG_HELPER: IOError writing to output file "
            f"{output_file_path}: {e_io!s}",
        )
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)
    except Exception as e_json:
        logger.debug(
            "DEBUG_HELPER: Exception during final JSON dump/file "
            f"write to {output_file_path}: {type(e_json).__name__}: {e_json!s}"
        )
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def main() -> None:
    package_list: list = []
    _reconfigure_logs()
    _args_checker()

    output_file_path = sys.argv[1]
    try:
        for dist in importlib.metadata.distributions():
            package_name = dist.name
            package_version = dist.version
            metadata = dist.metadata
            summary = metadata.get("Summary", "")

            current_project_urls = {}
            project_url_entries = metadata.get_all("Project-URL")
            if project_url_entries:
                for url_entry in project_url_entries:
                    try:
                        parts = [part.strip() for part in url_entry.split(",", 1)]
                        if len(parts) == PATHS_LEN:
                            label, url_value = parts
                            current_project_urls[label] = url_value
                    except AttributeError:
                        logger.debug("DEBUG_HELPER: AttributeError during Project-URL parsing.")
                        pass

            package_list.append(
                {
                    "name": package_name,
                    "version": package_version,
                    "summary": summary,
                    "project_urls": current_project_urls,
                }
            )
        _main_write_json(output_file_path, package_list)
    except Exception as e:
        error_payload = {"error": f"Error in _external_scanner_script.py: {e!s}"}
        logger.exception(json.dumps(error_payload))
        sys.exit(1)


if __name__ == "__main__":
    main()
