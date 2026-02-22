from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_population_lines(path: Path) -> list[str]:
    """Read a population file, returning one raw repr string per line (non-empty lines only)."""
    lines = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            if "<<<>>>" in raw:
                raw = raw.split("<<<>>>")[0]
            if "save_stats" in raw and ":" in raw:
                raw = raw.split(":", 1)[1].strip()
            lines.append(raw)
    except OSError as exc:
        logger.warning("Could not read population file %s: %s", path, exc)
    return lines


def write_population_lines(path: Path, dna_reprs: list[str]) -> None:
    """Write a list of genome repr strings to a population file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(dna_reprs) + "\n", encoding="utf-8")


def count_genomes(path: Path) -> int:
    """Return number of genomes in a population file."""
    return len(read_population_lines(path))
