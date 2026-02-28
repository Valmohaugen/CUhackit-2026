"""Tests for dashboard import-path bootstrap helpers."""

from __future__ import annotations

from pathlib import Path

from src.dashboard._bootstrap import ensure_project_root_on_path


def test_ensure_project_root_on_path_inserts_root_at_front() -> None:
    paths = ["/tmp/example", "/usr/local/lib/python3.11"]

    root = ensure_project_root_on_path(paths)

    assert paths[0] == root
    assert root == str(Path(__file__).resolve().parents[1])


def test_ensure_project_root_on_path_does_not_duplicate_existing_root() -> None:
    expected_root = str(Path(__file__).resolve().parents[1])
    paths = ["/tmp/example", expected_root, "/usr/local/lib/python3.11"]

    root = ensure_project_root_on_path(paths)

    assert root == expected_root
    assert paths == ["/tmp/example", expected_root, "/usr/local/lib/python3.11"]
    assert paths.count(expected_root) == 1


def test_ensure_project_root_on_path_mutates_custom_list() -> None:
    paths = ["/tmp/example"]
    original_id = id(paths)

    ensure_project_root_on_path(paths)

    assert id(paths) == original_id
    assert len(paths) == 2
