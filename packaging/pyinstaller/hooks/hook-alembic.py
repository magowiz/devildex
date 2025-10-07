"""PyInstaller hook for Alembic.

This hook ensures that Alembic's migrations are correctly bundled when creating
a standalone executable with PyInstaller.
"""
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('alembic')
