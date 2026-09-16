"""Filesystem and runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Return the checkout root or per-user state root when installed."""
    override = os.environ.get("OVERSEER_HOME")
    if override:
        return Path(override).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "pyproject.toml").exists():
        return checkout
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "overseer"


def database_path() -> Path:
    override = os.environ.get("OVERSEER_DB")
    if override:
        return Path(override).expanduser().resolve()
    return project_root() / "data" / "generated" / "overseer.db"


def cache_path() -> Path:
    override = os.environ.get("OVERSEER_CACHE")
    if override:
        return Path(override).expanduser().resolve()
    return project_root() / "cache"


def schemas_path() -> Path:
    """Return packaged schema migrations."""
    return Path(__file__).resolve().parent / "schemas"


def sample_manifest_path() -> Path:
    """Return the packaged, reviewed Phase 1 manifest."""
    return Path(__file__).resolve().parent / "data" / "new-vegas-phase1.json"
