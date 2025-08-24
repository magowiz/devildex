# DevilDex
![DevilDex Logo](src/devildex/imgs/logo-final.png)

**DevilDex is a desktop application for discovering, generating, and viewing Python package documentation (docsets).** It scans your projects for dependencies, builds their documentation, and provides a unified interface to browse it all locally.

It's designed for developers who want quick, offline access to the documentation of the libraries they use every day.

## Key Features

-   **Project Scanning**: Automatically scans your Python projects (`pyproject.toml`, `requirements.txt`) to find all their dependencies.
-   **Docset Generation**: Uses tools like Sphinx, pdoc, and pydoctor to generate HTML documentation for your packages.
-   **Uniform Theming**: Applies a consistent and professional DevilDex theme across different documentation generators (Sphinx, pdoc3, pydoctor, MkDocs) for a unified viewing experience.
-   **Integrated Viewer**: A built-in browser view to read and navigate the generated docsets without leaving the application.
-   **Database Management**: Uses SQLAlchemy to keep track of your packages, projects, and available docsets.
-   **Cross-Platform GUI**: Built with the wxPython framework to run on multiple operating systems.

## Installation

### 1. System Dependencies
Before installing the application, you need to install several system packages required for `wxPython` and its dependencies.

**On Debian/Ubuntu-based systems:**
```bash
sudo apt-get update
sudo apt-get install -y \
    libgirepository1.0-dev \
    gobject-introspection \
    gir1.2-gtk-3.0 \
    gir1.2-webkit2-4.1 \
    python3-gi \
    python3-gi-cairo \
    python3-wxgtk4.0 \
    python3-wxgtk-webview4.0
```

### 2. Application Installation
Once the system dependencies are in place, you can install the Python packages using [Poetry](https://python-poetry.org/).

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd devildex
    ```

2.  **Install Python packages:**
    ```bash
    poetry install
    ```

## How to Run

Once everything is installed, you can run the application with:

```bash
poetry run devildex
```

## Contributing

Contributions are welcome! If you want to contribute to DevilDex, here’s how you can run the test suite.

**Running Tests**

The project uses `pytest`. To run the full test suite:

```bash
poetry run pytest
```

**Running UI Tests Headlessly**

The UI tests are designed to run in a headless environment (like in a CI pipeline) using `Xvfb`. To run them this way, use:

```bash
xvfb-run poetry run pytest
```

## License

This project is licensed under the [INSERT LICENSE NAME HERE] License. See the `LICENSE` file for more details.
