"""Tests for GoBreeder.gui.archive.population_file_reader.GenomeEntry."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from GoBreeder.gui.archive.population_file_reader import GenomeEntry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXAMPLE_DNA_REPR = "[('mov', ['X0', 'GP0']), ('add', ['X', 'Y', None]), ('mov', ['GP0', '0'])]"

EXPECTED_DNA = [
    ("mov", ["X0", "GP0"]),
    ("add", ["X", "Y", None]),
    ("mov", ["GP0", "0"]),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(**kwargs: object) -> GenomeEntry:
    """Create a :class:`GenomeEntry` with sensible defaults."""
    defaults: dict[str, object] = {
        "source_file": "population.py",
        "line_index": 0,
        "dna_repr": EXAMPLE_DNA_REPR,
    }
    defaults.update(kwargs)
    return GenomeEntry(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Basic creation
# ---------------------------------------------------------------------------


class TestGenomeEntryCreation:
    """Tests that :class:`GenomeEntry` can be created with valid data."""

    def test_creates_successfully(self) -> None:
        entry = _make_entry()
        assert entry.source_file == "population.py"
        assert entry.line_index == 0
        assert entry.dna_repr == EXAMPLE_DNA_REPR

    def test_source_archive_defaults_to_none(self) -> None:
        entry = _make_entry()
        assert entry.source_archive is None

    def test_stats_defaults_to_none(self) -> None:
        entry = _make_entry()
        assert entry.stats is None

    def test_fitness_defaults_to_none(self) -> None:
        entry = _make_entry()
        assert entry.fitness is None

    def test_source_archive_can_be_path(self) -> None:
        entry = _make_entry(source_archive=Path("/some/archive.tar"))
        assert entry.source_archive == Path("/some/archive.tar")

    def test_with_fitness_and_stats(self) -> None:
        entry = _make_entry(fitness=0.85, stats='{"wins": 5}')
        assert entry.fitness == pytest.approx(0.85)
        assert entry.stats == '{"wins": 5}'

    def test_filesystem_source_has_none_archive(self) -> None:
        """A genome loaded from a plain file should have source_archive=None."""
        entry = _make_entry(source_archive=None)
        assert entry.source_archive is None


# ---------------------------------------------------------------------------
# .dna computed property
# ---------------------------------------------------------------------------


class TestGenomeEntryDna:
    """Tests for the :attr:`GenomeEntry.dna` computed property."""

    def test_returns_list(self) -> None:
        entry = _make_entry()
        assert isinstance(entry.dna, list)

    def test_parses_correctly(self) -> None:
        entry = _make_entry()
        assert entry.dna == EXPECTED_DNA

    def test_first_instruction(self) -> None:
        entry = _make_entry()
        assert entry.dna[0] == ("mov", ["X0", "GP0"])

    def test_last_instruction(self) -> None:
        entry = _make_entry()
        assert entry.dna[-1] == ("mov", ["GP0", "0"])

    def test_none_operand_preserved(self) -> None:
        entry = _make_entry()
        assert entry.dna[1] == ("add", ["X", "Y", None])

    def test_empty_list_repr(self) -> None:
        entry = _make_entry(dna_repr="[]")
        assert entry.dna == []

    def test_malformed_repr_returns_empty_list(self) -> None:
        entry = _make_entry(dna_repr="NOT VALID PYTHON !!!")
        assert entry.dna == []

    def test_malformed_repr_no_exception(self) -> None:
        """Malformed dna_repr must never raise an exception."""
        entry = _make_entry(dna_repr="{invalid syntax")
        result = entry.dna
        assert result == []

    def test_single_instruction(self) -> None:
        entry = _make_entry(dna_repr="[('nop', [])]")
        assert entry.dna == [("nop", [])]


# ---------------------------------------------------------------------------
# .instruction_count computed property
# ---------------------------------------------------------------------------


class TestGenomeEntryInstructionCount:
    """Tests for the :attr:`GenomeEntry.instruction_count` computed property."""

    def test_counts_three_instructions(self) -> None:
        entry = _make_entry()
        assert entry.instruction_count == 3

    def test_empty_dna_count_zero(self) -> None:
        entry = _make_entry(dna_repr="[]")
        assert entry.instruction_count == 0

    def test_single_instruction_count(self) -> None:
        entry = _make_entry(dna_repr="[('nop', [])]")
        assert entry.instruction_count == 1

    def test_malformed_repr_count_zero(self) -> None:
        entry = _make_entry(dna_repr="totally broken")
        assert entry.instruction_count == 0


# ---------------------------------------------------------------------------
# JSON / model serialisation round-trip
# ---------------------------------------------------------------------------


class TestGenomeEntrySerialisation:
    """Tests for Pydantic v2 model serialisation."""

    def test_model_dump_contains_dna_repr(self) -> None:
        entry = _make_entry()
        data = entry.model_dump()
        assert data["dna_repr"] == EXAMPLE_DNA_REPR

    def test_model_dump_contains_computed_fields(self) -> None:
        entry = _make_entry()
        data = entry.model_dump()
        # computed_field values should be included in the dump
        assert "instruction_count" in data
        assert data["instruction_count"] == 3

    def test_model_dump_with_fitness(self) -> None:
        entry = _make_entry(fitness=0.85)
        data = entry.model_dump()
        assert data["fitness"] == pytest.approx(0.85)

    def test_model_dump_with_stats(self) -> None:
        entry = _make_entry(stats='{"wins": 5}')
        data = entry.model_dump()
        assert data["stats"] == '{"wins": 5}'

    def test_json_round_trip(self) -> None:
        """model_dump(mode='json') should produce fully JSON-serialisable output."""
        entry = _make_entry(fitness=0.5, stats='{"wins": 3}')
        json_str = json.dumps(entry.model_dump(mode="json"))
        loaded = json.loads(json_str)
        assert loaded["dna_repr"] == EXAMPLE_DNA_REPR
        assert loaded["instruction_count"] == 3
        assert loaded["fitness"] == pytest.approx(0.5)

    def test_source_archive_none_serialises(self) -> None:
        entry = _make_entry(source_archive=None)
        data = entry.model_dump()
        assert data["source_archive"] is None

    def test_source_archive_path_serialises(self) -> None:
        entry = _make_entry(source_archive=Path("/archives/run1.tar"))
        data = entry.model_dump()
        # Pydantic serialises Path objects as strings or Path depending on mode
        assert data["source_archive"] is not None
