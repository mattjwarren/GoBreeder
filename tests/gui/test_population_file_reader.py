"""Tests for GoBreeder.gui.archive.population_file_reader."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from GoBreeder.gui.archive.archive_reader import ArchiveEntry
from GoBreeder.gui.archive.population_file_reader import (
    GenomeEntry,
    read_population_file,
    read_population_from_archive,
)

# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

PLAIN_LINE_1 = "[('mov', ['X0', 'GP0']), ('add', ['X', 'Y', None])]"
PLAIN_LINE_2 = "[('nop', [])]"

STATS_LINE_1 = "[('mov', ['X0', 'GP0'])]<<<>>>{'wins': 5}<<<>>>0.75"
STATS_LINE_2 = "[('nop', [])]<<<>>>{'wins': 2}<<<>>>0.40"


def _write_population_file(tmp_path: Path, lines: list[str]) -> Path:
    """Write *lines* to a population file in *tmp_path* and return its path."""
    p = tmp_path / "population.py"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _make_archive(tmp_path: Path, internal_name: str, content: str) -> Path:
    """Create a plain tar archive in *tmp_path* with a single file."""
    archive_path = tmp_path / "archive.tar"
    data = content.encode("utf-8")
    info = tarfile.TarInfo(name=internal_name)
    info.size = len(data)
    with tarfile.open(archive_path, "w:") as tf:
        tf.addfile(info, io.BytesIO(data))
    return archive_path


# ---------------------------------------------------------------------------
# read_population_file – plain format
# ---------------------------------------------------------------------------


class TestReadPopulationFilePlain:
    """Tests for :func:`read_population_file` with plain DNA lines."""

    def test_returns_genome_entries(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [PLAIN_LINE_1, PLAIN_LINE_2])
        genomes = read_population_file(path)
        assert len(genomes) == 2

    def test_dna_repr_stored_correctly(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [PLAIN_LINE_1])
        genomes = read_population_file(path)
        assert genomes[0].dna_repr == PLAIN_LINE_1

    def test_line_index_is_correct(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [PLAIN_LINE_1, PLAIN_LINE_2])
        genomes = read_population_file(path)
        assert genomes[0].line_index == 0
        assert genomes[1].line_index == 1

    def test_source_file_set_to_path(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [PLAIN_LINE_1])
        genomes = read_population_file(path)
        assert genomes[0].source_file == str(path)

    def test_stats_and_fitness_none_for_plain(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [PLAIN_LINE_1])
        genomes = read_population_file(path)
        assert genomes[0].stats is None
        assert genomes[0].fitness is None

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, ["", PLAIN_LINE_1, ""])
        genomes = read_population_file(path)
        assert len(genomes) == 1

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        genomes = read_population_file(tmp_path / "missing.py")
        assert genomes == []

    def test_dna_parses_to_list(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [PLAIN_LINE_1])
        genomes = read_population_file(path)
        dna = genomes[0].dna
        assert isinstance(dna, list)
        assert dna[0] == ("mov", ["X0", "GP0"])


# ---------------------------------------------------------------------------
# read_population_file – stats-save format
# ---------------------------------------------------------------------------


class TestReadPopulationFileStatsSave:
    """Tests for :func:`read_population_file` with stats-save format lines."""

    def test_returns_correct_count(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [STATS_LINE_1, STATS_LINE_2])
        genomes = read_population_file(path)
        assert len(genomes) == 2

    def test_dna_repr_is_only_dna_part(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [STATS_LINE_1])
        genomes = read_population_file(path)
        assert "<<<>>>" not in genomes[0].dna_repr
        assert genomes[0].dna_repr == "[('mov', ['X0', 'GP0'])]"

    def test_stats_extracted(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [STATS_LINE_1])
        genomes = read_population_file(path)
        assert genomes[0].stats == "{'wins': 5}"

    def test_fitness_extracted(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [STATS_LINE_1])
        genomes = read_population_file(path)
        assert genomes[0].fitness == pytest.approx(0.75)

    def test_second_entry_fitness(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [STATS_LINE_1, STATS_LINE_2])
        genomes = read_population_file(path)
        assert genomes[1].fitness == pytest.approx(0.40)

    def test_dna_parses_correctly(self, tmp_path: Path) -> None:
        path = _write_population_file(tmp_path, [STATS_LINE_1])
        genomes = read_population_file(path)
        assert genomes[0].dna == [("mov", ["X0", "GP0"])]


# ---------------------------------------------------------------------------
# GenomeEntry – dna and instruction_count
# ---------------------------------------------------------------------------


class TestGenomeEntryProperties:
    """Tests for :class:`GenomeEntry` computed properties."""

    def _make(self, dna_repr: str) -> GenomeEntry:
        return GenomeEntry(source_file="test.py", line_index=0, dna_repr=dna_repr)

    def test_instruction_count_correct(self) -> None:
        entry = self._make("[('mov', ['X0', 'GP0']), ('nop', [])]")
        assert entry.instruction_count == 2

    def test_instruction_count_empty(self) -> None:
        entry = self._make("[]")
        assert entry.instruction_count == 0

    def test_malformed_repr_returns_empty_dna(self) -> None:
        entry = self._make("this is not valid python !!!")
        assert entry.dna == []
        assert entry.instruction_count == 0


# ---------------------------------------------------------------------------
# read_population_from_archive
# ---------------------------------------------------------------------------


class TestReadPopulationFromArchive:
    """Tests for :func:`read_population_from_archive`."""

    def _entry(self, archive_path: Path, internal_path: str) -> ArchiveEntry:
        return ArchiveEntry(archive_path=archive_path, internal_path=internal_path, size=0)

    def test_reads_plain_genomes(self, tmp_path: Path) -> None:
        content = PLAIN_LINE_1 + "\n" + PLAIN_LINE_2
        archive = _make_archive(tmp_path, "population.py", content)
        entry = self._entry(archive, "population.py")
        genomes = read_population_from_archive(entry)
        assert len(genomes) == 2

    def test_source_archive_set(self, tmp_path: Path) -> None:
        content = PLAIN_LINE_1
        archive = _make_archive(tmp_path, "population.py", content)
        entry = self._entry(archive, "population.py")
        genomes = read_population_from_archive(entry)
        assert genomes[0].source_archive == archive

    def test_source_file_is_internal_path(self, tmp_path: Path) -> None:
        content = PLAIN_LINE_1
        archive = _make_archive(tmp_path, "population.py", content)
        entry = self._entry(archive, "population.py")
        genomes = read_population_from_archive(entry)
        assert genomes[0].source_file == "population.py"

    def test_stats_save_format_in_archive(self, tmp_path: Path) -> None:
        content = STATS_LINE_1
        archive = _make_archive(tmp_path, "population.py", content)
        entry = self._entry(archive, "population.py")
        genomes = read_population_from_archive(entry)
        assert len(genomes) == 1
        assert genomes[0].fitness == pytest.approx(0.75)
        assert genomes[0].stats == "{'wins': 5}"

    def test_missing_member_returns_empty(self, tmp_path: Path) -> None:
        content = PLAIN_LINE_1
        archive = _make_archive(tmp_path, "population.py", content)
        entry = self._entry(archive, "nonexistent.py")
        genomes = read_population_from_archive(entry)
        assert genomes == []

    def test_dna_parses_correctly(self, tmp_path: Path) -> None:
        content = PLAIN_LINE_1
        archive = _make_archive(tmp_path, "population.py", content)
        entry = self._entry(archive, "population.py")
        genomes = read_population_from_archive(entry)
        assert genomes[0].dna[0] == ("mov", ["X0", "GP0"])
