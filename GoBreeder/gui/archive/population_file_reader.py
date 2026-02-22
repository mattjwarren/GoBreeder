from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field

from GoBreeder.gui.archive.archive_reader import ArchiveEntry, ArchiveReader

logger = logging.getLogger(__name__)


class GenomeEntry(BaseModel):
    """A single genome parsed from a population file.

    Attributes
    ----------
    source_archive:
        Path to the tar archive that contained the population file, or ``None``
        when the file was read directly from the filesystem.
    source_file:
        String path (or archive-internal path) of the population file.
    line_index:
        Zero-based index of this genome's line within the source file.
    dna_repr:
        Raw Python repr string for the DNA instruction list.
    stats:
        Optional repr string for the stats dict (stats-save format only).
    fitness:
        Optional floating-point fitness score (stats-save format only).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_archive: Path | None = None
    source_file: str
    line_index: int
    dna_repr: str
    stats: str | None = None
    fitness: float | None = None

    @computed_field  # type: ignore[misc]
    @property
    def dna(self) -> list[Any]:
        """Parse *dna_repr* and return the instruction list.

        Returns an empty list if the repr string cannot be evaluated safely.
        """
        logger.debug(
            "Parsing dna_repr for genome at %s line %d", self.source_file, self.line_index
        )
        try:
            return ast.literal_eval(self.dna_repr)
        except (SyntaxError, ValueError) as exc:
            logger.warning(
                "Failed to parse genome dna_repr at %s line %d: %s",
                self.source_file,
                self.line_index,
                exc,
            )
            return []

    @computed_field  # type: ignore[misc]
    @property
    def instruction_count(self) -> int:
        """Return the number of instructions in this genome."""
        return len(self.dna)


def _parse_line(raw_line: str) -> tuple[str, str | None, float | None]:
    """Parse a single population-file line.

    Supports both the plain DNA format and the stats-save format where parts
    are separated by ``<<<>>>``.

    Parameters
    ----------
    raw_line:
        A pre-stripped, non-empty line from a population file.

    Returns
    -------
    tuple[str, str | None, float | None]
        A ``(dna_repr, stats_repr, fitness)`` triple.  *stats_repr* and
        *fitness* are ``None`` for plain-format lines.
    """
    if "<<<>>>" in raw_line:
        parts = raw_line.split("<<<>>>")
        dna_repr = parts[0].strip()
        stats_repr = parts[1].strip() if len(parts) > 1 else None
        fitness_str = parts[2].strip() if len(parts) > 2 else None
        fitness: float | None = None
        if fitness_str:
            try:
                fitness = float(fitness_str)
            except (ValueError, TypeError):
                logger.warning("Could not parse fitness value %r", fitness_str)
        return dna_repr, stats_repr, fitness
    return raw_line.strip(), None, None


def read_population_file(path: Path) -> list[GenomeEntry]:
    """Read a population file from the local filesystem.

    Parameters
    ----------
    path:
        Path to the population file (plain text, one genome per line).

    Returns
    -------
    list[GenomeEntry]
        Parsed genome entries.  Returns an empty list if the file cannot be
        read.
    """
    logger.debug("Reading population file from filesystem: %s", path)
    genomes: list[GenomeEntry] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.error("Cannot read population file %s: %s", path, exc)
        return []

    for i, raw in enumerate(lines):
        raw = raw.strip()
        if not raw:
            continue
        # Handle save_stats format prefix (e.g. "save_stats: [...]")
        if "save_stats" in raw and ":" in raw:
            raw = raw.split(":", 1)[1].strip()
        dna_repr, stats_repr, fitness = _parse_line(raw)
        if not dna_repr:
            continue
        logger.debug("Parsed genome at line %d: dna_repr length=%d", i, len(dna_repr))
        genomes.append(
            GenomeEntry(
                source_file=str(path),
                line_index=i,
                dna_repr=dna_repr,
                stats=stats_repr,
                fitness=fitness,
            )
        )
    logger.debug("Loaded %d genome(s) from %s", len(genomes), path)
    return genomes


def read_population_from_archive(entry: ArchiveEntry) -> list[GenomeEntry]:
    """Read a population file from a tar archive entry.

    Parameters
    ----------
    entry:
        An :class:`~GoBreeder.gui.archive.archive_reader.ArchiveEntry`
        identifying a file inside a tar archive.

    Returns
    -------
    list[GenomeEntry]
        Parsed genome entries.  Returns an empty list if the entry cannot be
        read or parsed.
    """
    logger.debug(
        "Reading population from archive entry: %s / %s",
        entry.archive_path,
        entry.internal_path,
    )
    reader = ArchiveReader()
    raw_lines = reader.read_population_file(entry)
    genomes: list[GenomeEntry] = []
    for i, raw in enumerate(raw_lines):
        dna_repr, stats_repr, fitness = _parse_line(raw)
        if not dna_repr:
            continue
        logger.debug(
            "Parsed archive genome at index %d: dna_repr length=%d", i, len(dna_repr)
        )
        genomes.append(
            GenomeEntry(
                source_archive=entry.archive_path,
                source_file=entry.internal_path,
                line_index=i,
                dna_repr=dna_repr,
                stats=stats_repr,
                fitness=fitness,
            )
        )
    logger.debug(
        "Loaded %d genome(s) from archive entry %s/%s",
        len(genomes),
        entry.archive_path,
        entry.internal_path,
    )
    return genomes
