# Contributing Guide

We're excited you're interested in contributing to DevilDex! This guide will help you get started.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

The general contribution process is as follows:

1. **Fork** the repository.
2. **Clone** your fork locally.
3. **Create a branch** for your changes (`git checkout -b feature/your-feature-name` or `bugfix/bug-description`).
4. **Implement** your changes, ensuring you follow style guidelines and include appropriate tests.
5. **Run tests** to ensure everything works as expected.
6. **Commit** your changes with a clear and descriptive commit message.
7. **Push** your branch to your fork.
8. **Open a Pull Request** (PR) to the main repository.

## Setting Up the Development Environment

To start developing on DevilDex:

1. **Prerequisites**: Make sure you have Python (version 3.11+ recommended) and [Poetry](https://python-poetry.org/) installed.
2. **Clone the repository**:
    ```bash
    git clone https://github.com/magowiz/devildex.git
    cd devildex
    ```
3. **Install dependencies**:
    ```bash
    poetry install
    ```
    *Note for Linux Developers*: For `wxPython` to function correctly, especially its `WebView` component, ensure you have installed the necessary system dependencies as outlined in the "System Dependencies" section of the `README.md`.
4. **Run the application**:
    ```bash
    poetry run devildex
    ```

## Running Tests

It is crucial that all changes pass existing tests and that new tests are added for new features or bug fixes.

* **Run all tests**:
    ```bash
    poetry run pytest
    ```
* **Run UI tests headlessly (requires Xvfb on Linux)**:
    ```bash
    xvfb-run poetry run pytest
    ```
    *Note*: Tests involving the core application logic should instantiate `DevilDexCore` with an in-memory SQLite database for isolation: `core = DevilDexCore(database_url='sqlite:///:memory:')`.

## Code Style and Guidelines

* Follow the existing code style in the project.
* We use `ruff` for linting and formatting. Ensure your code is compliant.
* Add comments only when necessary to explain the *why* of a complex choice, not the *what*.

## Submitting Changes (Pull Request)

When opening a Pull Request:

* Provide a clear and concise description of the changes.
* Reference any related issues (e.g., `Fixes #123`, `Closes #456`).
* Ensure tests pass and the code is properly formatted.

## Reporting Bugs and Suggesting Features

If you find a bug or have an idea for a new feature, please open an issue on our [issue tracker](https://github.com/magowiz/devildex/issues).

Thank you for your contribution!