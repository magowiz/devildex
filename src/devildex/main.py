"""main application module."""

import os

import webview
from local_data_parse.common_read import \
    get_explicit_dependencies_from_project_config
from local_data_parse.venv_inventory import \
    get_installed_packages_with_project_urls

# pylint: disable=E0611


def scan_current_project():
    """Scan current project for explicit dependencies."""
    explicit = get_explicit_dependencies_from_project_config()
    docr = get_installed_packages_with_project_urls(explicit=explicit)
    return docr


class Api:

    def handle_select_project(self):
        """Simula la selezione di un progetto. In un'app reale, aprirebbe un dialogo nativo."""
        active_window = webview.active_window()
        if active_window:
            try:
                result = active_window.create_file_dialog(
                    webview.FOLDER_DIALOG, allow_multiple=False
                )

                if result and len(result) > 0:
                    selected_path = result[0]
                    print(f"Python: Selected folder - {selected_path}")
                    active_window.evaluate_js(
                        f"update_status_from_python('Elaborating folder: {os.path.basename(selected_path)}...')"
                    )
                    return {
                        "path": selected_path,
                        "message": "Project Path received!",
                    }
                else:
                    print("Python: No folder selected or dialog canceled.")
                    return {"path": None, "message": "No project selected."}
            except Exception as e:
                print(f"Error in file dialog: {e}")
                return {"path": None, "message": f"Error: {e}"}
        return {"path": None, "message": "The window is not available."}

    @staticmethod
    def some_other_python_function(param):
        print(f"Python: some_other_python_function called with: {param}")
        active_window = webview.active_window()
        if active_window:
            active_window.evaluate_js(
                f"typeof update_status_from_python === 'function' && update_status_from_python('some_other_python_function has received: {param}')"
            )
        return f"Python has received '{param}'"


def get_gui_path(file_name="index.html"):
    return os.path.join(os.path.dirname(__file__), "gui", file_name)


if __name__ == "__main__":
    api_instance = Api()
    gui_file_url = get_gui_path()
    if not os.path.exists(gui_file_url):
        if not gui_file_url.startswith("file://"):
            gui_file_url = "file://" + os.path.abspath(gui_file_url)
    print(f"Loading GUI from: {gui_file_url}")
    window = webview.create_window(
        "DevilDex",
        gui_file_url,
        js_api=api_instance,
        width=900,
        height=700,
        resizable=True,
        confirm_close=True,
    )
    webview.start()
    print("Application closed.")
