"""PyInstaller hook for SQLAlchemy.

This hook ensures that SQLAlchemy's internal modules and dialects are correctly
bundled when creating a standalone executable with PyInstaller.
"""
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('sqlalchemy')
