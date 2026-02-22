from __future__ import annotations

from pathlib import Path


def get_repo_root() -> Path:
    """Return the root of the GoBreeder repository."""
    return Path(__file__).parent.parent.parent.parent


def get_breed_source_dir() -> Path:
    """Return the canonical breed/ source directory."""
    return get_repo_root() / "GoBreeder" / "breed"


def get_user_data_dir() -> Path:
    """Return the user data directory for GoBreeder."""
    return Path.home() / ".gobreeder"
