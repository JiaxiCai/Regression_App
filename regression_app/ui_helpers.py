"""Reusable Qt layout helpers for Regression App.

This module is intentionally small in v0.3.0. New module-specific UI code
should migrate out of app.py into dedicated widgets over subsequent releases.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter


def configure_splitter(splitter: QSplitter, sizes=None, stretch=None):
    """Apply consistent non-collapsing splitter behavior."""
    splitter.setChildrenCollapsible(False)
    if stretch:
        for index, factor in enumerate(stretch):
            splitter.setStretchFactor(index, factor)
    if sizes:
        splitter.setSizes(list(sizes))
    return splitter
