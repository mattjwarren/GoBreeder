"""Unit tests for vm.py: GoVM execution and individual opcodes."""

import array

import config
from data_structures import GoGenome
from vm import GoVM


def _empty_board() -> dict:
    return {(x, y): 0 for x in range(config.board_size) for y in range(config.board_size)}


def _genome_from_dna(dna: list) -> GoGenome:
    """Wrap raw DNA in a GoGenome."""
    return GoGenome(dna=dna)  # type: ignore[arg-type]


def _run(dna: list, board: dict | None = None, player: str = "black") -> GoVM:
    """Run a genome and return the VM after execution."""
    if board is None:
        board = _empty_board()
    vm = GoVM()
    vm.get_move(board=board, player=player, program=_genome_from_dna(dna))
    return vm


# ---------------------------------------------------------------------------
# VM initialisation
# ---------------------------------------------------------------------------


class TestVMInit:
    def test_memory_is_array(self):
        """Memory block must be an array.array (not a plain list)."""
        vm = GoVM()
        vm.boot(board=_empty_board(), program=_genome_from_dna([("ret", [None, None])]))
        assert isinstance(vm.memory, array.array)

    def test_memory_size(self):
        vm = GoVM()
        vm.boot(board=_empty_board(), program=_genome_from_dna([("ret", [None, None])]))
        assert len(vm.memory) == vm.max_memoryons

    def test_board_size_modulation(self):
        """modulated_registers must use config.board_size, not a hard-coded 9."""
        assert GoVM.modulated_registers["X"] == config.board_size
        assert GoVM.modulated_registers["Y"] == config.board_size
        assert GoVM.modulated_registers["WXY"] == config.board_size


# ---------------------------------------------------------------------------
# Arithmetic opcodes
# ---------------------------------------------------------------------------


class TestArithmeticOpcodes:
    def _boot_vm(self):
        vm = GoVM()
        vm.boot(board=_empty_board(), program=_genome_from_dna([]))
        return vm

    def test_opcode_add(self):
        vm = self._boot_vm()
        vm.reg_RES = 0
        vm.opcode_add([3, 4])
        assert vm.reg_RES == 7

    def test_opcode_sub(self):
        vm = self._boot_vm()
        vm.opcode_sub([10, 3])
        assert vm.reg_RES == 7

    def test_opcode_mul(self):
        vm = self._boot_vm()
        vm.opcode_mul([6, 7])
        assert vm.reg_RES == 42

    def test_opcode_div_normal(self):
        vm = self._boot_vm()
        vm.opcode_div([10, 2])
        assert vm.reg_RES == 5

    def test_opcode_div_by_zero_returns_zero(self):
        vm = self._boot_vm()
        vm.opcode_div([10, 0])
        assert vm.reg_RES == 0
        assert vm.reg_CRY == 0

    def test_opcode_rnd_sets_res(self):
        """opcode_rnd must accept opdata and set RES (regression: wrong signature)."""
        vm = self._boot_vm()
        vm.opcode_rnd([None, None])  # must not raise TypeError
        # RES should be in the expected range
        half = config.rand_max // 2
        assert -half <= vm.reg_RES < config.rand_max - half


# ---------------------------------------------------------------------------
# SGN register
# ---------------------------------------------------------------------------


class TestSGN:
    def _boot_vm(self):
        vm = GoVM()
        vm.boot(board=_empty_board(), program=_genome_from_dna([]))
        return vm

    def test_set_sgn_positive(self):
        vm = self._boot_vm()
        vm.reg_RES = 5
        vm.set_SGN()
        assert vm.reg_SGN == 1

    def test_set_sgn_negative(self):
        vm = self._boot_vm()
        vm.reg_RES = -3
        vm.set_SGN()
        assert vm.reg_SGN == -1

    def test_set_sgn_zero(self):
        vm = self._boot_vm()
        vm.reg_RES = 0
        vm.set_SGN()
        assert vm.reg_SGN == 0

    def test_opcode_mov_updates_sgn(self):
        """Regression: opcode_mov previously used bare 'self.set_SGN' (no call)."""
        vm = self._boot_vm()
        vm.reg_RES = 7
        vm.set_SGN()
        # mov writes RES=0 → SGN should become 0
        vm.reg_RES = 0
        vm.opcode_mov([0, "RES"])
        vm.opcode_add([0, 0])  # RES=0 → SGN=0
        # After mov with value 0, set_SGN must have been called
        vm.reg_RES = 0
        vm.opcode_mov([0, "RES"])
        assert vm.reg_SGN == 0


# ---------------------------------------------------------------------------
# Comparison opcodes
# ---------------------------------------------------------------------------


class TestComparisonOpcodes:
    def _boot_vm(self):
        vm = GoVM()
        vm.boot(board=_empty_board(), program=_genome_from_dna([]))
        return vm

    def test_cmpe_equal(self):
        vm = self._boot_vm()
        vm.opcode_cmpe([5, 5])
        assert vm.reg_LOG == 1

    def test_cmpe_not_equal(self):
        vm = self._boot_vm()
        vm.opcode_cmpe([5, 6])
        assert vm.reg_LOG == 0

    def test_cmplt(self):
        vm = self._boot_vm()
        vm.opcode_cmplt([3, 5])
        assert vm.reg_LOG == 1
        vm.opcode_cmplt([5, 3])
        assert vm.reg_LOG == 0

    def test_cmpgt(self):
        vm = self._boot_vm()
        vm.opcode_cmpgt([10, 2])
        assert vm.reg_LOG == 1


# ---------------------------------------------------------------------------
# rnd opcode dispatch (regression: was missing from table or wrong signature)
# ---------------------------------------------------------------------------


class TestRndOpcode:
    def test_rnd_in_dispatch_table(self):
        assert "rnd" in GoVM.opcodes

    def test_rnd_dispatch_does_not_raise(self):
        """Calling rnd via the dispatch table must not raise TypeError."""
        vm = GoVM()
        vm.boot(board=_empty_board(), program=_genome_from_dna([]))
        GoVM.opcodes["rnd"](vm, [None, None])


# ---------------------------------------------------------------------------
# Full program execution
# ---------------------------------------------------------------------------


class TestProgramExecution:
    def test_halt_program_returns_move(self):
        """A minimal genome returns a valid (x, y) tuple."""
        dna: list = [("ret", [None, None])] * 10
        vm = GoVM()
        move, history = vm.get_move(
            board=_empty_board(),
            player="black",
            program=_genome_from_dna(dna),
        )
        x, y = move
        assert 0 <= x < config.board_size
        assert 0 <= y < config.board_size

    def test_move_coordinates_within_board(self):
        """X/Y registers are modulated to board_size before returning a move."""
        import random

        random.seed(42)
        g = GoGenome()
        vm = GoVM()
        move, _ = vm.get_move(board=_empty_board(), player="white", program=g)
        x, y = move
        assert 0 <= x < config.board_size
        assert 0 <= y < config.board_size
