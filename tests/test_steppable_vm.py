"""Unit tests for steppable_vm.py: SteppableGoVM generator-based execution."""

from __future__ import annotations

import config
from data_structures import GoGenome
from steppable_vm import BoardInfoSnapshot, SteppableGoVM, VMStepSnapshot
from vm import GoVM

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_board() -> dict:
    return {(x, y): 0 for x in range(config.board_size) for y in range(config.board_size)}


def _genome(dna: list) -> GoGenome:
    return GoGenome(dna=dna)  # type: ignore[arg-type]


def _boot(vm_instance: GoVM, dna: list, board: dict | None = None, player: str = "black") -> GoVM:
    if board is None:
        board = _empty_board()
    vm_instance.boot(board=board, program=_genome(dna))
    vm_instance.reg_PLAYER = GoVM.player_reg_lookup[player]
    return vm_instance


# ---------------------------------------------------------------------------
# BoardInfoSnapshot
# ---------------------------------------------------------------------------


class TestBoardInfoSnapshot:
    def test_fields_present(self):
        snap = BoardInfoSnapshot(values=[1, 2, 3], ptr=0, current_value=1)
        assert snap.values == [1, 2, 3]
        assert snap.ptr == 0
        assert snap.current_value == 1

    def test_current_value_none(self):
        snap = BoardInfoSnapshot(values=[], ptr=0, current_value=None)
        assert snap.current_value is None

    def test_captures_board_info_after_boot(self):
        svm = SteppableGoVM()
        _boot(svm, [("ret", [None, None])])
        board_info = svm._capture_board_info()
        assert isinstance(board_info, dict)
        for expected_key in ("blacks", "whites", "spaces", "white_freedoms", "black_freedoms", "all_stones"):
            assert expected_key in board_info
            bis = board_info[expected_key]
            assert isinstance(bis, BoardInfoSnapshot)
            assert isinstance(bis.values, list)
            assert isinstance(bis.ptr, int)


# ---------------------------------------------------------------------------
# VMStepSnapshot
# ---------------------------------------------------------------------------


class TestVMStepSnapshot:
    def test_all_required_fields_present(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        assert len(snapshots) > 0
        snap = snapshots[0]

        # Check all register fields are ints
        for field in (
            "reg_X", "reg_Y", "reg_RES", "reg_CRY", "reg_SGN", "reg_LOG",
            "reg_WXY", "reg_PLAYER",
            "reg_X0", "reg_X1", "reg_X2", "reg_X3", "reg_X4", "reg_X5", "reg_X6", "reg_X7",
            "reg_Y0", "reg_Y1", "reg_Y2", "reg_Y3", "reg_Y4", "reg_Y5", "reg_Y6", "reg_Y7",
            "reg_GP0", "reg_GP1", "reg_GP2", "reg_GP3", "reg_GP4", "reg_GP5", "reg_GP6", "reg_GP7",
        ):
            assert isinstance(getattr(snap, field), int), f"{field} should be int"

        # Boolean fields
        assert isinstance(snap.reg_PC_INTERRUPT, bool)
        assert isinstance(snap.reg_HALT, bool)
        assert isinstance(snap.halt, bool)

        # Sequence fields
        assert isinstance(snap.stack_top_10, list)
        assert isinstance(snap.memory_0_to_50, list)
        assert len(snap.memory_0_to_50) <= 50

        # Board fields
        assert isinstance(snap.board, dict)
        assert isinstance(snap.board_info, dict)

        # Instruction fields
        assert snap.current_instruction is not None
        assert isinstance(snap.current_instruction, tuple)
        assert isinstance(snap.canonical_opdata, list)

    def test_clock_field_type(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        assert isinstance(snapshots[0].clock, int)

    def test_pc_field_type(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        assert isinstance(snapshots[0].pc, int)

    def test_reg_stn_is_tuple(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        assert isinstance(snapshots[0].reg_STN, tuple)

    def test_move_xy_fields(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        snap = snapshots[-1]
        assert isinstance(snap.move_x, int)
        assert isinstance(snap.move_y, int)

    def test_board_dict_has_string_keys(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        board = snapshots[0].board
        for k in board.keys():
            assert isinstance(k, str), f"Board key {k!r} should be a string"


# ---------------------------------------------------------------------------
# step_generator: step count and termination
# ---------------------------------------------------------------------------


class TestStepGenerator:
    def test_single_instruction_genome_yields_one_snapshot(self):
        """A genome with one instruction yields exactly one snapshot."""
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        assert len(snapshots) == 1

    def test_two_instruction_genome_yields_two_snapshots(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        assert len(snapshots) == 2

    def test_max_clocks_limits_execution(self):
        """With max_clocks=1, generator stops after one instruction."""
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"]), ("mov", ["X", "GP2"])])
        snapshots = list(svm.step_generator(max_clocks=1))
        assert len(snapshots) == 1

    def test_empty_program_does_not_crash(self):
        """GoGenome([]) may add default instructions; step_generator must not crash."""
        svm = SteppableGoVM()
        _boot(svm, [])
        snapshots = list(svm.step_generator(max_clocks=10))
        # We just assert it runs without error and yields VMStepSnapshot instances.
        for snap in snapshots:
            assert isinstance(snap, VMStepSnapshot)

    def test_clock_increments_per_step(self):
        """Clock is incremented after each instruction; snapshot i has clock == i+1."""
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"]), ("mov", ["X", "GP2"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        for i, snap in enumerate(snapshots):
            assert snap.clock == i + 1, f"Expected clock={i + 1}, got {snap.clock}"

    def test_pc_starts_at_zero(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"])])
        snapshots = list(svm.step_generator(max_clocks=100))
        # First snapshot is captured after executing instruction 0, pc has already advanced
        assert snapshots[0].pc == 1

    def test_yields_vmstepsnapshot_instances(self):
        svm = SteppableGoVM()
        _boot(svm, [("mov", ["X", "GP0"])])
        for snap in svm.step_generator(max_clocks=10):
            assert isinstance(snap, VMStepSnapshot)

    def test_current_instruction_matches_program(self):
        """Each snapshot should record the instruction that was just executed."""
        dna = [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"])]
        svm = SteppableGoVM()
        _boot(svm, dna)
        snapshots = list(svm.step_generator(max_clocks=100))
        assert snapshots[0].current_instruction[0] == "mov"
        assert snapshots[1].current_instruction[0] == "mov"

    def test_step_by_step_instruction_tracking(self):
        """Step through instructions one at a time using the generator directly."""
        dna = [
            ("mov", ["X", "GP0"]),
            ("mov", ["Y", "GP1"]),
            ("mov", ["X", "GP2"]),
        ]
        svm = SteppableGoVM()
        _boot(svm, dna)
        gen = svm.step_generator(max_clocks=100)

        snap1 = next(gen)
        assert snap1.clock == 1  # clock is post-increment: first instruction -> clock=1
        assert snap1.current_instruction[0] == "mov"

        snap2 = next(gen)
        assert snap2.clock == 2
        assert snap2.current_instruction[0] == "mov"

        snap3 = next(gen)
        assert snap3.clock == 3

        # Generator should be exhausted now
        try:
            next(gen)
            assert False, "Expected StopIteration"
        except StopIteration:
            pass


# ---------------------------------------------------------------------------
# SteppableGoVM.get_move matches GoVM.get_move
# ---------------------------------------------------------------------------


class TestGetMoveConsistency:
    def test_get_move_returns_tuple(self):
        svm = SteppableGoVM()
        board = _empty_board()
        move, _ = svm.get_move(board=board, player="black", program=_genome([("mov", ["X", "GP0"])]))
        assert isinstance(move, tuple)
        assert len(move) == 2

    def test_get_move_coords_in_bounds(self):
        svm = SteppableGoVM()
        board = _empty_board()
        move, _ = svm.get_move(board=board, player="black", program=_genome([("mov", ["X", "GP0"])]))
        x, y = move
        assert 0 <= x < config.board_size
        assert 0 <= y < config.board_size

    def test_steppable_move_matches_plain_vm(self):
        """SteppableGoVM must produce the same move as GoVM for identical input."""
        dna = [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"])]
        board = _empty_board()

        plain_vm = GoVM()
        plain_move, _ = plain_vm.get_move(board=board, player="black", program=_genome(dna))

        step_vm = SteppableGoVM()
        step_move, _ = step_vm.get_move(board=board, player="black", program=_genome(dna))

        assert step_move == plain_move

    def test_steppable_reg_x_matches_plain_vm(self):
        """reg_X after execution must match between SteppableGoVM and GoVM."""
        dna = [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"])]
        board = _empty_board()

        plain_vm = GoVM()
        plain_vm.get_move(board=board, player="black", program=_genome(dna))

        step_vm = SteppableGoVM()
        step_vm.get_move(board=board, player="black", program=_genome(dna))

        assert step_vm.reg_X == plain_vm.reg_X
        assert step_vm.reg_Y == plain_vm.reg_Y

    def test_final_snapshot_move_xy_reflects_reg_values(self):
        """The last snapshot's move_x / move_y should reflect reg_X / reg_Y."""
        dna = [("mov", ["X", "GP0"]), ("mov", ["Y", "GP1"])]
        svm = SteppableGoVM()
        _boot(svm, dna)
        snapshots = list(svm.step_generator(max_clocks=100))
        last = snapshots[-1]
        assert last.move_x == last.reg_X
        assert last.move_y == last.reg_Y

    def test_player_black_register(self):
        """Player register should be set to -1 for black."""
        svm = SteppableGoVM()
        board = _empty_board()
        svm.get_move(board=board, player="black", program=_genome([("mov", ["X", "GP0"])]))
        assert svm.reg_PLAYER == GoVM.player_reg_lookup["black"]

    def test_player_white_register(self):
        """Player register should be set to 1 for white."""
        svm = SteppableGoVM()
        board = _empty_board()
        svm.get_move(board=board, player="white", program=_genome([("mov", ["X", "GP0"])]))
        assert svm.reg_PLAYER == GoVM.player_reg_lookup["white"]
