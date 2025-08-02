"""
Configuration file for pytest.

This file defines shared fixtures for the test suite.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def wx_app_session():
    """
    Create a wx.App instance for the entire test session.

    This is a session-scoped, autouse fixture that ensures a `wx.App` object
    exists before any tests are run. It is crucial for testing wxPython
    applications to prevent `AttributeError: partially initialized module 'wx'`
    errors that can occur during test collection or execution.
    """
    import wx

    # wx.App(False) creates a non-GUI app instance, which is ideal for testing.
    app = wx.App(False)
    yield app