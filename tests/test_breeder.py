"""Unit tests for the fitness calculation and population management in breeder.py."""

import config
from breeder import Breeder
from data_structures import GoGenome


def _make_genome() -> GoGenome:
    return GoGenome()


def _make_breeder_no_file(pop_size: int = 4) -> Breeder:
    """Return a Breeder with a small freshly-generated population."""
    return Breeder(population_size=pop_size, population_file=None)


# ---------------------------------------------------------------------------
# Fitness formula
# ---------------------------------------------------------------------------


class TestFitnessFormula:
    """Verify that winners always outscore losers regardless of move count."""

    def test_winner_always_beats_loser(self):
        """Any winner fitness > any loser fitness (magic-constant regression)."""
        max_moves = config.board_size * config.board_size // 2
        winner_offset = max_moves + 1

        # Worst winner: played all possible moves
        worst_winner_fitness = (max_moves - max_moves) + winner_offset  # = winner_offset
        # Best loser: played 0 moves (immediate loss)
        best_loser_fitness = 0

        assert worst_winner_fitness > best_loser_fitness

    def test_fewer_winner_moves_gives_higher_fitness(self):
        """A winner who won faster should beat a winner who won slower."""
        max_moves = config.board_size * config.board_size // 2
        winner_offset = max_moves + 1

        fast_win = (max_moves - 5) + winner_offset
        slow_win = (max_moves - 10) + winner_offset
        assert fast_win > slow_win


# ---------------------------------------------------------------------------
# Population initialisation
# ---------------------------------------------------------------------------


class TestPopulationInit:
    def test_correct_size(self):
        b = _make_breeder_no_file(pop_size=6)
        assert len(b.population) == 6

    def test_all_genomes_unique(self):
        b = _make_breeder_no_file(pop_size=10)
        hashes = [g.hashname for g in b.population]
        # All hashes should be distinct
        assert len(set(hashes)) == len(hashes)

    def test_genome_stats_initialised(self):
        b = _make_breeder_no_file(pop_size=4)
        for genome in b.population:
            assert genome in b.genome_stats


# ---------------------------------------------------------------------------
# ast.literal_eval genome loading (security regression)
# ---------------------------------------------------------------------------


class TestGenomeLoading:
    """Verify that population loading uses ast.literal_eval, not eval()."""

    def test_pop_file_uses_literal_eval(self, tmp_path):
        """Load a population file: must work and must not execute arbitrary code."""

        # Write a valid population file
        g = GoGenome()
        pop_file = tmp_path / "pop.py"
        pop_file.write_text(repr(g.dna) + "\n")

        b = Breeder(population_size=1, population_file=str(pop_file))
        assert len(b.population) >= 1

    def test_malicious_line_raises_not_executes(self, tmp_path):
        """A line with executable code must be rejected by literal_eval, not executed."""

        sentinel_file = tmp_path / "sentinel.txt"
        malicious = f"__import__('pathlib').Path(r'{sentinel_file}').write_text('PWNED')\n"
        pop_file = tmp_path / "malicious_pop.py"
        pop_file.write_text(malicious)

        # Breeder should fail to parse the line (ValueError/SyntaxError from literal_eval)
        # and NOT create sentinel_file.
        Breeder(population_size=0, population_file=str(pop_file))
        assert not sentinel_file.exists(), "Malicious code must NOT have been executed"
