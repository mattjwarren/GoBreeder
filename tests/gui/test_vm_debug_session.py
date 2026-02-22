"""Tests for VMDebugWorker and VMDebugSession."""
from __future__ import annotations

import pytest

import config  # type: ignore[import]
import steppable_vm  # type: ignore[import]  # breed/ is on sys.path via conftest
from data_structures import GoGenome  # type: ignore[import]

from GoBreeder.gui.vm_debug.vm_debug_session import VMDebugSession, VMDebugWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_board() -> dict:
    """Return a standard 9x9 empty board."""
    return {(x, y): 0 for x in range(config.board_size) for y in range(config.board_size)}


def _minimal_dna() -> list:
    """Single instruction – program ends naturally after one step."""
    return [("mov", ["X", "X"])]


def _five_instruction_dna() -> list:
    """Five valid instructions that run and terminate naturally."""
    return [
        ("mov", ["X", "X"]),
        ("mov", ["Y", "Y"]),
        ("mov", ["X", "GP0"]),
        ("mov", ["Y", "GP1"]),
        ("ret", [None, None]),
    ]


def _make_worker() -> VMDebugWorker:
    return VMDebugWorker()


# ---------------------------------------------------------------------------
# VMDebugWorker unit tests (no Qt event loop needed for load / step)
# ---------------------------------------------------------------------------


class TestVMDebugWorkerLoad:
    def test_load_sets_initial_snapshot(self) -> None:
        worker = _make_worker()
        worker.load(_minimal_dna(), {}, "black")
        assert worker._vm is not None
        assert worker._last_snapshot is not None
        assert worker._last_snapshot.clock == 0

    def test_load_empty_dna_generates_genome_and_does_not_crash(self) -> None:
        """Empty DNA triggers GoGenome.genesis(); vm boots with a random genome."""
        worker = _make_worker()
        worker.load([], {}, "black")
        assert worker._vm is not None
        assert worker._last_snapshot is not None

    def test_load_sets_player_white(self) -> None:
        worker = _make_worker()
        worker.load(_minimal_dna(), {}, "white")
        assert worker._vm is not None
        expected = steppable_vm.SteppableGoVM.player_reg_lookup["white"]
        assert worker._vm.reg_PLAYER == expected

    def test_load_sets_player_black(self) -> None:
        worker = _make_worker()
        worker.load(_minimal_dna(), {}, "black")
        assert worker._vm is not None
        expected = steppable_vm.SteppableGoVM.player_reg_lookup["black"]
        assert worker._vm.reg_PLAYER == expected

    def test_load_accepts_explicit_board(self) -> None:
        worker = _make_worker()
        worker.load(_minimal_dna(), _empty_board(), "black")
        assert worker._vm is not None
        assert worker._last_snapshot is not None


class TestVMDebugWorkerStep:
    def test_step_emits_snapshot_ready(self, qtbot) -> None:
        worker = _make_worker()
        worker.load(_five_instruction_dna(), {}, "black")
        signals: list = []
        worker.snapshot_ready.connect(lambda s: signals.append(s))

        worker.step()

        assert len(signals) == 1
        assert signals[0].clock >= 0

    def test_step_advances_clock(self, qtbot) -> None:
        worker = _make_worker()
        worker.load(_five_instruction_dna(), {}, "black")
        snapshots: list = []
        worker.snapshot_ready.connect(lambda s: snapshots.append(s))

        worker.step()
        worker.step()

        assert len(snapshots) == 2
        assert snapshots[1].clock > snapshots[0].clock

    def test_step_past_end_emits_execution_finished(self, qtbot) -> None:
        """Stepping past the last instruction triggers execution_finished."""
        worker = _make_worker()
        worker.load(_minimal_dna(), {}, "black")
        finished: list = []
        worker.execution_finished.connect(lambda s: finished.append(s))

        worker.step()  # executes the single instruction
        worker.step()  # generator exhausted -> execution_finished

        assert len(finished) >= 1


class TestVMDebugWorkerPause:
    def test_pause_emits_paused(self, qtbot) -> None:
        worker = _make_worker()
        worker.load(_five_instruction_dna(), {}, "black")
        worker.step()  # advance once so there's a last_snapshot

        paused: list = []
        worker.paused.connect(lambda s: paused.append(s))
        worker.pause()

        assert len(paused) == 1

    def test_pause_without_prior_step_does_not_crash(self, qtbot) -> None:
        """pause() with last_snapshot from load() should emit paused."""
        worker = _make_worker()
        worker.load(_five_instruction_dna(), {}, "black")
        paused: list = []
        worker.paused.connect(lambda s: paused.append(s))
        worker.pause()
        assert len(paused) == 1


class TestVMDebugWorkerReset:
    def test_reset_resets_clock_to_zero(self, qtbot) -> None:
        worker = _make_worker()
        worker.load(_five_instruction_dna(), {}, "black")
        worker.step()
        worker.step()
        assert worker._last_snapshot is not None
        assert worker._last_snapshot.clock > 0

        paused_after_reset: list = []
        worker.paused.connect(lambda s: paused_after_reset.append(s))
        worker.reset()

        assert len(paused_after_reset) == 1
        assert paused_after_reset[0].clock == 0

    def test_reset_clears_generator_allowing_re_step(self, qtbot) -> None:
        worker = _make_worker()
        worker.load(_five_instruction_dna(), {}, "black")

        snapshots_before: list = []
        worker.snapshot_ready.connect(lambda s: snapshots_before.append(s))
        worker.step()
        worker.step()
        assert len(snapshots_before) == 2

        worker.reset()

        snapshots_after: list = []
        worker.snapshot_ready.connect(lambda s: snapshots_after.append(s))
        worker.step()
        assert len(snapshots_after) >= 1
        # Clock increments to 1 on the first step after reset (incremented before yield)
        assert snapshots_after[0].clock == 1


class TestStepGeneratorCount:
    def test_step_generator_yields_per_instruction(self) -> None:
        vm_instance = steppable_vm.SteppableGoVM()
        dna = _five_instruction_dna()
        genome = GoGenome(dna=dna)  # type: ignore[arg-type]
        vm_instance.boot(board=_empty_board(), program=genome)
        vm_instance.reg_PLAYER = steppable_vm.SteppableGoVM.player_reg_lookup["black"]

        snapshots = list(vm_instance.step_generator(max_clocks=4000))
        # Should yield exactly one snapshot per instruction
        assert len(snapshots) == len(dna)

    def test_step_generator_single_instruction(self) -> None:
        vm_instance = steppable_vm.SteppableGoVM()
        dna = _minimal_dna()
        genome = GoGenome(dna=dna)  # type: ignore[arg-type]
        vm_instance.boot(board=_empty_board(), program=genome)
        vm_instance.reg_PLAYER = steppable_vm.SteppableGoVM.player_reg_lookup["black"]

        snapshots = list(vm_instance.step_generator(max_clocks=4000))
        assert len(snapshots) == 1


# ---------------------------------------------------------------------------
# VMDebugSession integration tests
# ---------------------------------------------------------------------------


class TestVMDebugSession:
    def test_session_load_and_step_emits_snapshot_ready(self, qtbot, request) -> None:
        session = VMDebugSession()
        request.addfinalizer(session.stop_thread)
        session.load(_five_instruction_dna(), {}, "black")

        with qtbot.waitSignal(session.snapshot_ready, timeout=2000) as blocker:
            session.step()

        assert blocker.signal_triggered

    def test_session_after_last_step_emits_execution_finished(self, qtbot, request) -> None:
        """Stepping past end of a 1-instruction program emits execution_finished."""
        session = VMDebugSession()
        request.addfinalizer(session.stop_thread)
        session.load(_minimal_dna(), {}, "black")

        # Execute the single instruction first
        with qtbot.waitSignal(session.snapshot_ready, timeout=2000):
            session.step()

        # Now step again - generator exhausted, execution_finished fires
        with qtbot.waitSignal(session.execution_finished, timeout=2000):
            session.step()

    def test_session_stop_thread_joins_cleanly(self, qtbot) -> None:
        session = VMDebugSession()
        session.load(_minimal_dna(), {}, "black")
        session.stop_thread()
        assert not session._thread.isRunning()
