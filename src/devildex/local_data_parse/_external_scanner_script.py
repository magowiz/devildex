import importlib.metadata
import json
import logging
import sys

PATHS_LEN = 2
logger = logging.getLogger(__name__)
def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    package_list = []
    try:
        for dist in importlib.metadata.distributions():
            package_name = dist.name
            package_version = dist.version
            metadata = dist.metadata

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
                        pass

            package_list.append({
                "name": package_name,
                "version": package_version,
                "project_urls": current_project_urls,
            })

    except Exception as e:
        error_payload = {"error": f"Errore in _external_scanner_script.py: {e!s}"}
        logger.exception(json.dumps(error_payload))
        sys.exit(1)

    logger.info(json.dumps(package_list))
    sys.exit(0)

if __name__ == "__main__":
    main()
