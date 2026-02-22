"""Unit tests for board_info.py: get_board_info and get_surrounding_states."""

import config
from board_info import get_board_info, get_surrounding_states


def _empty_board() -> dict:
    """Return a blank 9x9 board (all zeros = empty)."""
    return {(x, y): 0 for x in range(config.board_size) for y in range(config.board_size)}


def _board_with(placements: dict) -> dict:
    """Return a board with specified stone placements on top of empty."""
    board = _empty_board()
    board.update(placements)
    return board


# ---------------------------------------------------------------------------
# get_board_info
# ---------------------------------------------------------------------------


class TestGetBoardInfo:
    def test_empty_board_all_spaces(self):
        board = _empty_board()
        blacks, whites, spaces, wf, bf, legal, illegal, all_stones = get_board_info(board)
        assert len(spaces.values) == config.board_size**2
        assert len(blacks.values) == 0
        assert len(whites.values) == 0

    def test_black_stone_counted(self):
        board = _board_with({(4, 4): -1})
        blacks, whites, spaces, *_ = get_board_info(board)
        assert (4, 4) in blacks
        assert (4, 4) not in whites
        assert (4, 4) not in spaces

    def test_white_stone_counted(self):
        board = _board_with({(2, 3): 1})
        blacks, whites, spaces, *_ = get_board_info(board)
        assert (2, 3) in whites
        assert (2, 3) not in blacks

    def test_legal_moves_equals_spaces(self):
        board = _board_with({(0, 0): -1})
        *_, legal, illegal, all_stones = get_board_info(board)
        total = config.board_size**2
        assert len(legal.values) == total - 1

    def test_all_stones_contains_both_colors(self):
        board = _board_with({(0, 0): -1, (1, 1): 1})
        *_, all_stones = get_board_info(board)
        assert (0, 0) in all_stones
        assert (1, 1) in all_stones

    def test_black_freedom_detected(self):
        """An empty square adjacent to a black stone is a black freedom."""
        board = _board_with({(4, 4): -1})
        _, _, _, wf, bf, *_ = get_board_info(board)
        # (4,5), (4,3), (3,4), (5,4) are all orthogonal neighbours of (4,4)
        neighbours = [(4, 5), (4, 3), (3, 4), (5, 4)]
        found = any(n in bf for n in neighbours)
        assert found, "Expected at least one black-freedom square near a black stone"


# ---------------------------------------------------------------------------
# get_surrounding_states
# ---------------------------------------------------------------------------


class TestGetSurroundingStates:
    def test_straight_neighbours_centre(self):
        board = _board_with({(4, 3): -1, (4, 5): 1})
        blacks, whites, spaces = get_surrounding_states(board, (4, 4), stoneset="straight")
        assert (4, 3) in blacks
        assert (4, 5) in whites

    def test_diagonal_coords_bug_fixed(self):
        """Regression: (-1,-1) appeared twice; (-1,1) was missing (typo bug)."""
        # Place a stone at the (-1,1) offset from (5,5) → (4,6)
        board = _board_with({(4, 6): -1})
        blacks, whites, spaces = get_surrounding_states(board, (5, 5), stoneset="diagonal")
        assert (4, 6) in blacks, "(4,6) is a diagonal neighbour of (5,5) at offset (-1,1)"

    def test_out_of_bounds_ignored(self):
        """Neighbours that fall outside the board must not cause KeyError."""
        board = _empty_board()
        blacks, whites, spaces = get_surrounding_states(board, (0, 0), stoneset="all")
        # corner – only 2 straight neighbours and 1 diagonal are in-bounds
        assert len(blacks) + len(whites) + len(spaces) <= 3

    def test_all_empty_neighbours(self):
        board = _empty_board()
        blacks, whites, spaces = get_surrounding_states(board, (4, 4), stoneset="straight")
        assert len(blacks) == 0
        assert len(whites) == 0
        assert len(spaces) == 4
