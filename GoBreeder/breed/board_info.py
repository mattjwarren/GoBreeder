"""Board-state analysis utilities for GoBreeder.

Provides ``get_board_info`` (board-wide state collections) and
``get_surrounding_states`` (neighbour queries) used by the VM.
"""

from __future__ import annotations

from typing import Literal

import config
import data_structures

Coord = tuple[int, int]
Board = dict[Coord, int]  # values: -1 black, 0 empty, 1 white
Stoneset = Literal["all", "straight", "diagonal"]


def get_board_info(
    board: Board,
    xmin: int = 0,
    ymin: int = 0,
    xmax: int | None = None,
    ymax: int | None = None,
) -> tuple[
    data_structures.CircularList,  # blacks
    data_structures.CircularList,  # whites
    data_structures.CircularList,  # spaces
    data_structures.CircularList,  # white_freedoms
    data_structures.CircularList,  # black_freedoms
    data_structures.CircularList,  # legal_moves  (= spaces)
    data_structures.CircularList,  # illegal_moves (= blacks+whites)
    data_structures.CircularList,  # all_stones   (= blacks+whites)
]:
    """Return eight circular-list state collections for the board."""
    if xmax is None:
        xmax = config.board_size - 1
    if ymax is None:
        ymax = config.board_size - 1
    # states, B blacks, W whites, S spaces, BF Black Freedoms, WF White Freedoms,
    # LM legal moves, IM illegal moves
    # SM stupid moves //managed by mediator//
    # WM winning moves (moves that win) //managed by mediator//
    # BG - black groups
    # WG - White groups
    # testing gitkraken commit remove me

    blacks = data_structures.CircularList()
    whites = data_structures.CircularList()
    spaces = data_structures.CircularList()
    white_freedoms = data_structures.CircularList()
    black_freedoms = data_structures.CircularList()

    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            if board[(x, y)] == -1:
                state_type = blacks
            elif board[(x, y)] == 0:
                state_type = spaces

                local_blacks, local_whites, _local_spaces = get_surrounding_states(
                    board=board, coords=(x, y), stoneset="straight"
                )
                white_freedoms.add_value((x, y)) if local_whites else ()
                black_freedoms.add_value((x, y)) if local_blacks else ()

            elif board[(x, y)] == 1:
                state_type = whites

            state_type.add_value((x, y))

    legal_moves = spaces
    illegal_moves = blacks + whites
    all_stones = blacks + whites
    return (
        blacks,
        whites,
        spaces,
        white_freedoms,
        black_freedoms,
        legal_moves,
        illegal_moves,
        all_stones,
    )  # TODO: !!!!<><><><><><<><><< moves and all stones as opcodes


def get_surrounding_states(
    board: Board,
    coords: Coord = (0, 0),
    stoneset: Stoneset = "all",
) -> tuple[list[Coord], list[Coord], list[Coord]]:
    """Return (black_stones, white_stones, empty_spaces) surrounding *coords*."""
    xc, yc = coords
    straight_coords = [(0, 1), (-1, 0), (1, 0), (0, -1)]
    diagonal_coords = [(-1, -1), (1, 1), (-1, 1), (1, -1)]
    all_coords = straight_coords + diagonal_coords
    if stoneset == "straight":
        get_list = straight_coords
    elif stoneset == "diagonal":
        get_list = diagonal_coords
    else:
        get_list = all_coords

    black_stones = []
    white_stones = []
    spaces = []
    for x, y in get_list:
        x = x + xc
        y = y + yc
        if (not x < 0) and (not x > config.board_size - 1) and (not y < 0) and (not y > config.board_size - 1):
            if board[(x, y)] == -1:
                state_type = black_stones
            elif board[(x, y)] == 0:
                state_type = spaces
            elif board[(x, y)] == 1:
                state_type = white_stones
            state_type.append((x, y))
    return black_stones, white_stones, spaces
