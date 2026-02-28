"""Helpers for running the dashboard from script or package entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_project_root_on_path(path_list: list[str] | None = None) -> str:
    """Ensure the project root is available for absolute ``src.*`` imports."""
    root = str(Path(__file__).resolve().parents[2])
    target = sys.path if path_list is None else path_list

    if root not in target:
        target.insert(0, root)

    return root
