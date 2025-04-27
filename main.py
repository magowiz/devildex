import sys

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
)
from PySide6.QtCore import Qt

from local_data_parse.common_read import get_explicit_dependencies_from_project_config
from local_data_parse.venv_inventory import get_installed_packages_with_docs_urls


def scan_current_project():
    explicit = get_explicit_dependencies_from_project_config()
    docr = get_installed_packages_with_docs_urls(explicit=explicit)
    return docr


class DevilDexMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DevilDex - Python Documentation ")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        folder_layout = QHBoxLayout()

        self.folder_label = QLabel("Project Folder:")
        self.folder_path_edit = QLineEdit()
        self.browse_button = QPushButton("Sfoglia...")

        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_path_edit)
        folder_layout.addWidget(self.browse_button)

        main_layout.addLayout(folder_layout)

        self.scan_button = QPushButton("Scan Project")
        main_layout.addWidget(self.scan_button)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(
            ["Package Name", "Version", "Documentation URL"]
        )

        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSortingEnabled(True)

        main_layout.addWidget(self.results_table)

        self.browse_button.clicked.connect(self.browse_folder)
        self.scan_button.clicked.connect(self.scan_project)
        self.results_table.cellClicked.connect(self.open_url_from_table)

    def browse_folder(self):
        """Open a file dialog to select project folder."""
        folder_selected = QFileDialog.getExistingDirectory(
            self, "Select Project Folder"
        )
        if folder_selected:
            self.folder_path_edit.setText(folder_selected)

    def scan_project(self):
        """Scan of project in specified folder or in current env."""
        project_folder = self.folder_path_edit.text()

        self.results_table.setRowCount(0)

        if not project_folder:
            res = scan_current_project()
            self.display_results(res)
        else:
            print(f"Scan la project folder: {project_folder}")  # Placeholder
            pass

    def display_results(self, results_data):
        """Populates table with results."""
        self.results_table.setRowCount(len(results_data))

        for row_index, pkg_info in enumerate(results_data):
            name_item = QTableWidgetItem(pkg_info.get("name", "N/A"))
            version_item = QTableWidgetItem(pkg_info.get("version", "N/A"))
            url_item = QTableWidgetItem(pkg_info.get("docs_url", "N/A"))

            name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable)
            version_item.setFlags(version_item.flags() ^ Qt.ItemIsEditable)
            url_item.setFlags(url_item.flags() ^ Qt.ItemIsEditable)

            self.results_table.setItem(row_index, 0, name_item)
            self.results_table.setItem(row_index, 1, version_item)
            self.results_table.setItem(row_index, 2, url_item)

    def open_url_from_table(self, row, column):
        """Opens the URL in the documentation URL column if clicked."""
        doc_url_column_index = 2

        if column == doc_url_column_index:
            item = self.results_table.item(row, column)
            if item is not None:
                url_text = item.text()
                if url_text and url_text != "N/A":  # Controlla che l'URL esista e non sia "N/A"
                    url = QUrl(url_text)
                    QDesktopServices.openUrl(url)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = DevilDexMainWindow()
    main_window.show()

    sys.exit(app.exec())
