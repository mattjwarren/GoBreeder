from __future__ import annotations

import logging
import os
import sys
from typing import Any

# Ensure breed/ directory is importable (steppable_vm lives there, not in package).
_BREED_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "breed")
)
if _BREED_DIR not in sys.path:
    sys.path.insert(0, _BREED_DIR)

import data_structures  # type: ignore[import]  # noqa: E402
import steppable_vm  # type: ignore[import]  # noqa: E402
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot  # noqa: E402

logger = logging.getLogger(__name__)


class VMDebugWorker(QObject):
    """Worker that runs in a QThread and drives SteppableGoVM execution."""

    snapshot_ready = Signal(object)      # VMStepSnapshot
    execution_finished = Signal(object)  # final VMStepSnapshot
    paused = Signal(object)              # VMStepSnapshot at pause point
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._vm: Any = None  # SteppableGoVM instance
        self._generator: Any = None
        self._running: bool = False
        self._step_delay_ms: int = 0
        self._timer: QTimer | None = None
        self._last_snapshot: Any = None

    @staticmethod
    def _make_empty_board() -> dict:
        """Return a standard empty 9×9 Go board."""
        return {(x, y): 0 for x in range(9) for y in range(9)}

    def load(self, dna: list, board: dict, player: str) -> None:
        """Load a genome and set up for execution.

        If *board* is an empty dict a standard 9×9 empty board is used.
        """
        try:
            effective_board = board if board else self._make_empty_board()
            genome = data_structures.GoGenome(dna=dna) if dna else data_structures.GoGenome()
            self._vm = steppable_vm.SteppableGoVM()
            self._vm.boot(board=effective_board, program=genome)
            self._vm.reg_PLAYER = self._vm.player_reg_lookup[player]
            self._generator = None
            self._running = False
            self._last_snapshot = self._vm._capture_snapshot()
            logger.debug(
                "VMDebugWorker loaded genome (%d instructions), player=%s",
                len(dna),
                player,
            )
        except Exception as exc:
            logger.exception("Failed to load genome: %s", exc)
            self.error_occurred.emit(str(exc))

    @Slot()
    def step(self) -> None:
        """Advance one instruction."""
        if self._vm is None:
            return
        if self._generator is None:
            self._generator = self._vm.step_generator(max_clocks=4000)
        try:
            snapshot = next(self._generator)
            self._last_snapshot = snapshot
            self.snapshot_ready.emit(snapshot)
            if snapshot.halt:
                self._generator = None
                self.execution_finished.emit(snapshot)
        except StopIteration:
            self._generator = None
            if self._last_snapshot is not None:
                self.execution_finished.emit(self._last_snapshot)
        except Exception as exc:
            logger.exception("Error during step: %s", exc)
            self.error_occurred.emit(str(exc))

    @Slot(int)
    def set_step_delay(self, delay_ms: int) -> None:
        self._step_delay_ms = delay_ms

    @Slot()
    def run(self) -> None:
        """Run continuously until pause or end."""
        if self._vm is None:
            return
        self._running = True
        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        interval = max(0, self._step_delay_ms)
        self._timer.setInterval(interval)
        self._timer.timeout.connect(self._run_step)
        self._timer.start()

    @Slot()
    def pause(self) -> None:
        """Pause continuous run."""
        self._running = False
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        if self._last_snapshot is not None:
            self.paused.emit(self._last_snapshot)

    @Slot()
    def reset(self) -> None:
        """Reset generator to initial state (re-run boot)."""
        self._running = False
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        self._generator = None
        if self._vm is not None:
            self._vm.initialise_memories()
            self._last_snapshot = self._vm._capture_snapshot()
            self.paused.emit(self._last_snapshot)

    def _run_step(self) -> None:
        if not self._running:
            return
        if self._vm is None:
            self._running = False
            return
        if self._generator is None:
            self._generator = self._vm.step_generator(max_clocks=4000)
        try:
            snapshot = next(self._generator)
            self._last_snapshot = snapshot
            self.snapshot_ready.emit(snapshot)
            if snapshot.halt:
                self._running = False
                self._generator = None
                if self._timer:
                    self._timer.stop()
                self.execution_finished.emit(snapshot)
        except StopIteration:
            self._running = False
            self._generator = None
            if self._timer:
                self._timer.stop()
            if self._last_snapshot is not None:
                self.execution_finished.emit(self._last_snapshot)
        except Exception as exc:
            self._running = False
            self.error_occurred.emit(str(exc))


class VMDebugSession(QObject):
    """
    High-level VM debug session. Manages a VMDebugWorker in a QThread.

    Uses Qt signals/slots for all cross-thread communication with the worker.
    Callers interact only with this class.
    """

    snapshot_ready = Signal(object)      # VMStepSnapshot
    execution_finished = Signal(object)
    paused = Signal(object)
    error_occurred = Signal(str)

    # Internal signals to dispatch commands to the worker thread.
    _step_requested = Signal()
    _run_requested = Signal()
    _pause_requested = Signal()
    _reset_requested = Signal()
    _delay_changed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = VMDebugWorker()
        self._worker.moveToThread(self._thread)

        # Forward worker outputs to session signals.
        self._worker.snapshot_ready.connect(self.snapshot_ready)
        self._worker.execution_finished.connect(self.execution_finished)
        self._worker.paused.connect(self.paused)
        self._worker.error_occurred.connect(self.error_occurred)

        # Connect command signals to worker slots (cross-thread via QueuedConnection).
        self._step_requested.connect(self._worker.step)
        self._run_requested.connect(self._worker.run)
        self._pause_requested.connect(self._worker.pause)
        self._reset_requested.connect(self._worker.reset)
        self._delay_changed.connect(self._worker.set_step_delay)

        self._thread.start()

    def load(self, dna: list, board: dict, player: str) -> None:
        # Direct call is safe: load() is called from GUI thread during initialisation
        # before any step/run commands are issued.
        self._worker.load(dna, board, player)

    def step(self) -> None:
        self._step_requested.emit()

    def run(self) -> None:
        self._run_requested.emit()

    def pause(self) -> None:
        self._pause_requested.emit()

    def reset(self) -> None:
        self._reset_requested.emit()

    def set_step_delay(self, delay_ms: int) -> None:
        self._delay_changed.emit(delay_ms)

    def stop_thread(self) -> None:
        """Cleanly stop the worker thread."""
        self._thread.quit()
        self._thread.wait(3000)
