"""Platform-aware relative-path equivalence helpers for planning and moves."""

from __future__ import annotations

import os
from pathlib import Path


def _key(path: Path) -> str:
    """Return the platform's normalized comparison form for a filesystem path."""
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def resolved_path(root: Path, relative_path: str) -> Path:
    return (root / Path(relative_path)).resolve(strict=False)


def relative_path_key(root: Path, relative_path: str) -> str:
    return _key(resolved_path(root, relative_path))


def paths_equivalent(root: Path, first: str, second: str) -> bool:
    return relative_path_key(root, first) == relative_path_key(root, second)


def is_within_relative_path(root: Path, child: str, parent: str) -> bool:
    """Return whether child is equal to or below parent under OS semantics."""
    child_key = relative_path_key(root, child)
    parent_key = relative_path_key(root, parent)
    try:
        return os.path.commonpath((child_key, parent_key)) == parent_key
    except ValueError:
        return False


def conflicts_with_source_directory(
    root: Path,
    destination_relative_path: str,
    source_directories: tuple[str, ...] | list[str],
) -> bool:
    """Prevent organized destinations from being placed inside source dirs."""
    return any(
        is_within_relative_path(root, destination_relative_path, source_directory)
        for source_directory in source_directories
    )
