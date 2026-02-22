from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.run_state import RunState
from GoBreeder.gui.utils.paths import get_repo_root

logger = logging.getLogger(__name__)

_BREED_SOURCE_FILES = [
    "__init__.py",
    "board_info.py",
    "breeder.py",
    "breeding_genome.py",
    "config.py",
    "current_population.py",
    "data_structures.py",
    "go_engine.py",
    "logging_config.py",
    "mediator.py",
    "play_gtp.py",
    "simple_go.py",
    "steppable_vm.py",
    "threaded_fileops.py",
    "vm.py",
    "vm_running_genome.py",
]

_BINARY_FILES = [
    "ref_v0.1_exe",
]

_SUBDIRS_TO_COPY = [
    "java",
    "windows",
]


class DeploymentError(Exception):
    """Raised when deployment creation or deletion fails."""


class DeploymentFactory:
    """Creates new deployment directory trees from the repo source."""

    def create(self, name: str, parent_dir: Path, repo_root: Path | None = None) -> DeploymentModel:
        """
        Create a new deployment.

        Args:
            name: Deployment name (used as directory name).
            parent_dir: Parent directory where deployment_dir will be created.
            repo_root: (optional) Repo root; defaults to auto-detected repo root.

        Returns:
            A DeploymentModel for the new deployment.
        """
        if repo_root is None:
            repo_root = get_repo_root()

        source_breed_dir = repo_root / "GoBreeder" / "breed"
        deployment_dir = parent_dir / name
        breed_dir = deployment_dir / "breed"

        if deployment_dir.exists():
            raise DeploymentError(f"Deployment directory already exists: {deployment_dir}")

        logger.debug("Creating deployment %r at %s", name, deployment_dir)
        breed_dir.mkdir(parents=True)

        # Copy Python source files
        for fname in _BREED_SOURCE_FILES:
            src = source_breed_dir / fname
            if src.exists():
                dst = breed_dir / fname
                shutil.copy2(src, dst)
                logger.debug("Copied %s -> %s", src, dst)
            else:
                logger.debug("Source file not found (skipped): %s", src)

        # Copy binary files
        for fname in _BINARY_FILES:
            src = source_breed_dir / fname
            if src.exists():
                shutil.copy2(src, breed_dir / fname)

        # Copy subdirectories (java/, windows/)
        for subdir_name in _SUBDIRS_TO_COPY:
            src_subdir = source_breed_dir / subdir_name
            if src_subdir.exists():
                dst_subdir = breed_dir / subdir_name
                shutil.copytree(src_subdir, dst_subdir)
                logger.debug("Copied subdir %s -> %s", src_subdir, dst_subdir)

        # Generate config.py with correct basepath
        _write_config(breed_dir)

        # Create empty current_population.py (with comment) if not already copied
        pop_file = breed_dir / "current_population.py"
        if not pop_file.exists():
            pop_file.write_text("# Empty population — inject a genome set to begin breeding.\n")

        model = DeploymentModel(
            name=name,
            deployment_dir=deployment_dir,
            created_at=datetime.now(),
            run_state=RunState.IDLE,
        )
        logger.info("Created deployment %r at %s", name, deployment_dir)
        return model


def _write_config(breed_dir: Path) -> None:
    """Write a config.py with basepath set to breed_dir."""
    abs_path = os.path.abspath(str(breed_dir))
    config_content = f"""# Auto-generated config for this deployment.
# basepath is set to this deployment's breed/ directory.
import os
import shutil


def _choose_sep(path):
    if "/" in path and "\\\\" not in path:
        return "/"
    if "\\\\" in path and "/" not in path:
        return "\\\\"
    return os.sep


def _ensure_trailing_sep(path):
    sep = _choose_sep(path)
    if not path.endswith(sep):
        return path + sep
    return path


def _join_path(base, *parts):
    sep = _choose_sep(base)
    out = base.rstrip("/\\\\")
    for part in parts:
        out = out + sep + str(part).strip("/\\\\")
    return out


basepath = _ensure_trailing_sep({abs_path!r})
java_basepath = _ensure_trailing_sep(_join_path(basepath, "java"))

_java_bin = shutil.which("java") or "java"

def set_basepath(new_basepath):
    global basepath, java_basepath
    basepath = _ensure_trailing_sep(new_basepath)
    java_basepath = _ensure_trailing_sep(_join_path(basepath, "java"))

board_size = 9
vm_running_genome_file = _join_path(basepath, "vm_running_genome.py")
runlog = _join_path(basepath, "runlog.txt")
"""
    (breed_dir / "config.py").write_text(config_content)
    logger.debug("Wrote config.py with basepath=%r", abs_path)
