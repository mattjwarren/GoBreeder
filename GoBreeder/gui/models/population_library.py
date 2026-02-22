from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field
from PySide6.QtCore import QObject, Signal

from GoBreeder.gui.models.deployment import DeploymentModel

logger = logging.getLogger(__name__)

_DEFAULT_LIBRARY_DIR = Path.home() / ".gobreeder" / "populations"
_DEFAULT_REGISTRY_PATH = Path.home() / ".gobreeder" / "library.json"


class PopulationRecord(BaseModel):
    name: str
    file_path: Path
    genome_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    notes: str = ""

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        if kwargs.get("mode") == "json":
            for key in ("file_path",):
                if key in data and isinstance(data[key], Path):
                    data[key] = str(data[key])
        return data


class PopulationLibraryError(Exception):
    pass


class PopulationLibrary(QObject):
    """Manages a persistent library of named population files."""

    library_changed = Signal()

    def __init__(
        self,
        library_dir: Path | None = None,
        registry_path: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._library_dir = library_dir or _DEFAULT_LIBRARY_DIR
        self._registry_path = registry_path or _DEFAULT_REGISTRY_PATH
        self._records: list[PopulationRecord] = []
        self._library_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def add(self, name: str, source_path: Path | None = None) -> PopulationRecord:
        """Add a new population to the library. If source_path is given, copy from it."""
        if any(r.name == name for r in self._records):
            raise PopulationLibraryError(f"Population '{name}' already exists in library.")
        file_path = self._library_dir / f"{name}.pop"
        if source_path is not None:
            shutil.copy2(source_path, file_path)
        else:
            file_path.write_text("# Empty population\n")
        genome_count = _count_genomes(file_path)
        record = PopulationRecord(
            name=name,
            file_path=file_path,
            genome_count=genome_count,
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )
        self._records.append(record)
        self._save()
        self.library_changed.emit()
        logger.debug("Added population %r to library (%d genomes)", name, genome_count)
        return record

    def add_from_dna_list(self, name: str, dna_reprs: list[str]) -> PopulationRecord:
        """Add a population from a list of raw genome repr strings."""
        if any(r.name == name for r in self._records):
            raise PopulationLibraryError(f"Population '{name}' already exists in library.")
        file_path = self._library_dir / f"{name}.pop"
        file_path.write_text("\n".join(dna_reprs) + "\n", encoding="utf-8")
        record = PopulationRecord(
            name=name,
            file_path=file_path,
            genome_count=len(dna_reprs),
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )
        self._records.append(record)
        self._save()
        self.library_changed.emit()
        return record

    def delete(self, record: PopulationRecord) -> None:
        if record.file_path.exists():
            record.file_path.unlink()
        self._records = [r for r in self._records if r.name != record.name]
        self._save()
        self.library_changed.emit()
        logger.debug("Deleted population %r from library", record.name)

    def rename(self, record: PopulationRecord, new_name: str) -> PopulationRecord:
        if any(r.name == new_name for r in self._records):
            raise PopulationLibraryError(f"Population '{new_name}' already exists in library.")
        new_path = self._library_dir / f"{new_name}.pop"
        if record.file_path.exists():
            shutil.move(str(record.file_path), str(new_path))
        updated = record.model_copy(update={"name": new_name, "file_path": new_path, "modified_at": datetime.now()})
        self._records = [updated if r.name == record.name else r for r in self._records]
        self._save()
        self.library_changed.emit()
        return updated

    def inject_into_deployment(self, record: PopulationRecord, deployment: DeploymentModel) -> None:
        """Copy the population file into the deployment's current_population.py."""
        if deployment.is_running():
            raise PopulationLibraryError(
                f"Cannot inject into running deployment '{deployment.name}'. Stop it first."
            )
        if not record.file_path.exists():
            raise PopulationLibraryError(f"Population file not found: {record.file_path}")
        target = deployment.population_file_path()
        shutil.copy2(record.file_path, target)
        logger.info("Injected population %r into deployment %r", record.name, deployment.name)

    def list_all(self) -> list[PopulationRecord]:
        return list(self._records)

    def _save(self) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump(mode="json") for r in self._records]
        self._registry_path.write_text(json.dumps(data, indent=2, default=str))

    def _load(self) -> None:
        if not self._registry_path.exists():
            return
        try:
            raw = json.loads(self._registry_path.read_text())
            self._records = [PopulationRecord.model_validate(item) for item in raw]
        except Exception as exc:
            logger.warning("Failed to load population library: %s", exc)
            self._records = []


def _count_genomes(path: Path) -> int:
    try:
        return sum(
            1 for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        )
    except OSError:
        return 0
