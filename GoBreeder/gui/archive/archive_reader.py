from __future__ import annotations

import logging
import tarfile
from pathlib import Path
from typing import IO

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_POPULATION_FILE_PATTERNS = (
    "population",
    "current_population",
)

_SUPPORTED_EXTENSIONS = {".tar", ".gz", ".bz2", ".xz"}


class ArchiveEntry(BaseModel):
    """Represents a file within an archive."""

    archive_path: Path
    internal_path: str
    size: int

    def is_population_file(self) -> bool:
        """Return True if this entry looks like a population file.

        Checks that the filename contains a known population-file pattern and
        ends with the ``.py`` extension.
        """
        name = Path(self.internal_path).name.lower()
        return any(pat in name for pat in _POPULATION_FILE_PATTERNS) and name.endswith(".py")


class ArchiveReader:
    """Reads tar archive files and finds population files within them."""

    def list_files(self, archive_path: Path) -> list[ArchiveEntry]:
        """List all regular files contained in the archive.

        Parameters
        ----------
        archive_path:
            Path to a tar (optionally compressed) archive file.

        Returns
        -------
        list[ArchiveEntry]
            All file entries found in the archive.  Returns an empty list on
            any I/O or format error.
        """
        logger.debug("Listing files in archive: %s", archive_path)
        entries: list[ArchiveEntry] = []
        try:
            with tarfile.open(archive_path, "r:*") as tf:
                for member in tf.getmembers():
                    if member.isfile():
                        logger.debug("Found file in archive: %s (size=%d)", member.name, member.size)
                        entries.append(
                            ArchiveEntry(
                                archive_path=archive_path,
                                internal_path=member.name,
                                size=member.size,
                            )
                        )
        except (tarfile.TarError, OSError) as exc:
            logger.error("Failed to list archive %s: %s", archive_path, exc)
        logger.debug("Found %d files in archive %s", len(entries), archive_path)
        return entries

    def find_population_files(self, archive_path: Path) -> list[ArchiveEntry]:
        """Find entries inside *archive_path* that appear to be population files.

        Parameters
        ----------
        archive_path:
            Path to a tar (optionally compressed) archive file.

        Returns
        -------
        list[ArchiveEntry]
            Entries whose name matches a known population-file pattern.
        """
        logger.debug("Searching for population files in archive: %s", archive_path)
        results = [e for e in self.list_files(archive_path) if e.is_population_file()]
        logger.debug("Found %d population file(s) in %s", len(results), archive_path)
        return results

    def read_population_file(self, entry: ArchiveEntry) -> list[str]:
        """Read a population file from inside an archive and return raw genome lines.

        Each returned string is a stripped, non-empty line from the population
        file.  Lines are returned as-is (including any ``<<<>>>`` stats-save
        separator) so that callers can perform their own parsing.

        Parameters
        ----------
        entry:
            The :class:`ArchiveEntry` identifying the file within the archive.

        Returns
        -------
        list[str]
            Raw genome lines, one per genome.  Returns an empty list on error.
        """
        logger.debug(
            "Reading population file %s from archive %s",
            entry.internal_path,
            entry.archive_path,
        )
        lines: list[str] = []
        try:
            with tarfile.open(entry.archive_path, "r:*") as tf:
                member = tf.getmember(entry.internal_path)
                f: IO[bytes] | None = tf.extractfile(member)
                if f is None:
                    logger.warning(
                        "Could not extract %s from archive", entry.internal_path
                    )
                    return []
                content = f.read().decode("utf-8", errors="replace")
                for raw in content.splitlines():
                    raw = raw.strip()
                    if not raw:
                        continue
                    if "save_stats" in raw and ":" in raw:
                        raw = raw.split(":", 1)[1].strip()
                    lines.append(raw)
        except (tarfile.TarError, KeyError, OSError) as exc:
            logger.error(
                "Failed to read %s from %s: %s",
                entry.internal_path,
                entry.archive_path,
                exc,
            )
        logger.debug(
            "Read %d genome line(s) from %s/%s",
            len(lines),
            entry.archive_path,
            entry.internal_path,
        )
        return lines
