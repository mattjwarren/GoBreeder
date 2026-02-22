"""Tests for GoBreeder.gui.archive.archive_reader."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

from GoBreeder.gui.archive.archive_reader import ArchiveEntry, ArchiveReader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLAIN_CONTENT = (
    "[('mov', ['X0', 'GP0']), ('add', ['X', 'Y', None])]\n"
    "[('nop', [])]\n"
)

_STATS_CONTENT = (
    "[('mov', ['X0', 'GP0'])]<<<>>>{'wins': 5}<<<>>>0.75\n"
    "[('nop', [])]<<<>>>{'wins': 2}<<<>>>0.40\n"
)


def _make_tar(tmp_path: Path, filename: str, content: str, compress: str = "") -> Path:
    """Create a tar archive in *tmp_path* containing a single file.

    Parameters
    ----------
    tmp_path:
        Directory in which to write the archive.
    filename:
        Name of the inner file within the archive.
    content:
        Text content for the inner file.
    compress:
        Compression suffix: ``""`` for plain tar, ``"gz"`` for gzip,
        ``"bz2"`` for bzip2.
    """
    ext = f".tar.{compress}" if compress else ".tar"
    archive_path = tmp_path / f"test_archive{ext}"
    mode = f"w:{compress}" if compress else "w:"
    data = content.encode("utf-8")
    info = tarfile.TarInfo(name=filename)
    info.size = len(data)
    with tarfile.open(archive_path, mode) as tf:
        tf.addfile(info, io.BytesIO(data))
    return archive_path


# ---------------------------------------------------------------------------
# ArchiveEntry.is_population_file
# ---------------------------------------------------------------------------


class TestArchiveEntryIsPopulationFile:
    """Unit tests for :meth:`ArchiveEntry.is_population_file`."""

    def _entry(self, internal_path: str) -> ArchiveEntry:
        return ArchiveEntry(archive_path=Path("/fake.tar"), internal_path=internal_path, size=0)

    def test_population_py_matches(self) -> None:
        assert self._entry("some/dir/population.py").is_population_file() is True

    def test_current_population_py_matches(self) -> None:
        assert self._entry("current_population.py").is_population_file() is True

    def test_nested_path_matches(self) -> None:
        assert self._entry("run1/output/population.py").is_population_file() is True

    def test_non_py_extension_no_match(self) -> None:
        assert self._entry("population.txt").is_population_file() is False

    def test_unrelated_py_file_no_match(self) -> None:
        assert self._entry("genome_utils.py").is_population_file() is False

    def test_empty_path_no_match(self) -> None:
        assert self._entry("").is_population_file() is False

    def test_case_insensitive(self) -> None:
        assert self._entry("POPULATION.PY").is_population_file() is True


# ---------------------------------------------------------------------------
# ArchiveReader.list_files
# ---------------------------------------------------------------------------


class TestArchiveReaderListFiles:
    """Tests for :meth:`ArchiveReader.list_files`."""

    def test_returns_all_files(self, tmp_path: Path) -> None:
        archive_path = _make_tar(tmp_path, "population.py", _PLAIN_CONTENT)
        reader = ArchiveReader()
        entries = reader.list_files(archive_path)
        assert len(entries) == 1
        assert entries[0].internal_path == "population.py"

    def test_entry_has_correct_size(self, tmp_path: Path) -> None:
        content = _PLAIN_CONTENT
        archive_path = _make_tar(tmp_path, "population.py", content)
        reader = ArchiveReader()
        entries = reader.list_files(archive_path)
        assert entries[0].size == len(content.encode("utf-8"))

    def test_entry_archive_path_matches(self, tmp_path: Path) -> None:
        archive_path = _make_tar(tmp_path, "population.py", _PLAIN_CONTENT)
        reader = ArchiveReader()
        entries = reader.list_files(archive_path)
        assert entries[0].archive_path == archive_path

    def test_corrupt_archive_returns_empty(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.tar"
        bad.write_bytes(b"not a tar file")
        reader = ArchiveReader()
        entries = reader.list_files(bad)
        assert entries == []

    def test_missing_archive_returns_empty(self, tmp_path: Path) -> None:
        reader = ArchiveReader()
        entries = reader.list_files(tmp_path / "nonexistent.tar")
        assert entries == []

    def test_multiple_files(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "multi.tar"
        with tarfile.open(archive_path, "w:") as tf:
            for name, text in [("population.py", _PLAIN_CONTENT), ("other.txt", "hello")]:
                data = text.encode()
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        reader = ArchiveReader()
        entries = reader.list_files(archive_path)
        assert len(entries) == 2
        names = {e.internal_path for e in entries}
        assert names == {"population.py", "other.txt"}


# ---------------------------------------------------------------------------
# ArchiveReader.find_population_files
# ---------------------------------------------------------------------------


class TestArchiveReaderFindPopulationFiles:
    """Tests for :meth:`ArchiveReader.find_population_files`."""

    def test_finds_population_file(self, tmp_path: Path) -> None:
        archive_path = _make_tar(tmp_path, "population.py", _PLAIN_CONTENT)
        reader = ArchiveReader()
        results = reader.find_population_files(archive_path)
        assert len(results) == 1
        assert results[0].internal_path == "population.py"

    def test_ignores_non_population_file(self, tmp_path: Path) -> None:
        archive_path = _make_tar(tmp_path, "readme.txt", "hello")
        reader = ArchiveReader()
        results = reader.find_population_files(archive_path)
        assert results == []

    def test_mixed_files_returns_only_population(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "mixed.tar"
        with tarfile.open(archive_path, "w:") as tf:
            for name, text in [
                ("population.py", _PLAIN_CONTENT),
                ("current_population.py", _PLAIN_CONTENT),
                ("unrelated.py", "x=1"),
            ]:
                data = text.encode()
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        reader = ArchiveReader()
        results = reader.find_population_files(archive_path)
        names = {r.internal_path for r in results}
        assert names == {"population.py", "current_population.py"}

    def test_corrupt_archive_returns_empty(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.tar"
        bad.write_bytes(b"\x00" * 10)
        reader = ArchiveReader()
        assert reader.find_population_files(bad) == []


# ---------------------------------------------------------------------------
# ArchiveReader.read_population_file
# ---------------------------------------------------------------------------


class TestArchiveReaderReadPopulationFile:
    """Tests for :meth:`ArchiveReader.read_population_file`."""

    def _entry(self, archive_path: Path, internal_path: str = "population.py") -> ArchiveEntry:
        return ArchiveEntry(archive_path=archive_path, internal_path=internal_path, size=0)

    def test_reads_plain_lines(self, tmp_path: Path) -> None:
        archive_path = _make_tar(tmp_path, "population.py", _PLAIN_CONTENT)
        reader = ArchiveReader()
        lines = reader.read_population_file(self._entry(archive_path))
        assert len(lines) == 2
        assert lines[0].startswith("[('mov'")
        assert lines[1].startswith("[('nop'")

    def test_stats_save_format_lines_preserved(self, tmp_path: Path) -> None:
        archive_path = _make_tar(tmp_path, "population.py", _STATS_CONTENT)
        reader = ArchiveReader()
        lines = reader.read_population_file(self._entry(archive_path))
        # Full raw lines are returned; callers split on <<<>>> themselves
        assert all("<<<>>>" in line for line in lines)
        assert lines[0].startswith("[('mov'")

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        content = "\n\n[('nop', [])]\n\n"
        archive_path = _make_tar(tmp_path, "population.py", content)
        reader = ArchiveReader()
        lines = reader.read_population_file(self._entry(archive_path))
        assert lines == ["[('nop', [])]"]

    def test_gzip_archive(self, tmp_path: Path) -> None:
        archive_path = _make_tar(tmp_path, "population.py", _PLAIN_CONTENT, compress="gz")
        reader = ArchiveReader()
        lines = reader.read_population_file(self._entry(archive_path))
        assert len(lines) == 2

    def test_missing_member_returns_empty(self, tmp_path: Path) -> None:
        archive_path = _make_tar(tmp_path, "population.py", _PLAIN_CONTENT)
        reader = ArchiveReader()
        entry = ArchiveEntry(
            archive_path=archive_path, internal_path="does_not_exist.py", size=0
        )
        result = reader.read_population_file(entry)
        assert result == []

    def test_corrupt_archive_returns_empty(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.tar"
        bad.write_bytes(b"corrupted")
        reader = ArchiveReader()
        result = reader.read_population_file(self._entry(bad))
        assert result == []
