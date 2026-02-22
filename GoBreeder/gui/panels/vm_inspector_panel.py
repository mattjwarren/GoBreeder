from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GoBreeder.gui.models.app_state import AppState
from GoBreeder.gui.vm_debug.vm_debug_session import VMDebugSession
from GoBreeder.gui.widgets.board_widget import BoardWidget
from GoBreeder.gui.widgets.genome_code_view import GenomeCodeView

logger = logging.getLogger(__name__)


class RegisterPanel(QWidget):
    """Scrollable register display panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(2)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        GROUPS = [
            ("Control", ["pc", "clock", "HALT", "PC_INTERRUPT", "PC_INTERRUPT_A"]),
            ("Output (Move)", ["X", "Y"]),
            ("Arithmetic / Flags", ["RES", "CRY", "SGN", "LOG"]),
            ("Board", ["PLAYER", "STN", "WXY"]),
            ("X Working", [f"X{i}" for i in range(8)]),
            ("Y Working", [f"Y{i}" for i in range(8)]),
            ("General Purpose", [f"GP{i}" for i in range(8)]),
        ]
        for group_name, regs in GROUPS:
            box = QGroupBox(group_name)
            box_layout = QFormLayout(box)
            for reg in regs:
                lbl = QLabel("—")
                lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                box_layout.addRow(f"{reg}:", lbl)
                self._labels[reg] = lbl
            layout.addWidget(box)

        # Memory
        mem_box = QGroupBox("Memory [0:50]")
        mem_layout = QVBoxLayout(mem_box)
        self._mem_table = QTableWidget(50, 2)
        self._mem_table.setHorizontalHeaderLabels(["Addr", "Value"])
        self._mem_table.setFixedHeight(200)
        self._mem_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        mem_layout.addWidget(self._mem_table)
        layout.addWidget(mem_box)

        # Stack
        stack_box = QGroupBox("Stack (top 10)")
        stack_layout = QVBoxLayout(stack_box)
        self._stack_label = QLabel("—")
        self._stack_label.setWordWrap(True)
        stack_layout.addWidget(self._stack_label)
        layout.addWidget(stack_box)

        # Board info
        bi_box = QGroupBox("Board Info Iterators")
        bi_layout = QFormLayout(bi_box)
        self._bi_labels: dict[str, QLabel] = {}
        for name in ("blacks", "whites", "spaces", "white_freedoms", "black_freedoms", "all_stones"):
            lbl = QLabel("—")
            bi_layout.addRow(f"{name}:", lbl)
            self._bi_labels[name] = lbl
        layout.addWidget(bi_box)

        layout.addStretch()

    def _set(self, reg: str, value: Any) -> None:
        lbl = self._labels.get(reg)
        if lbl:
            lbl.setText(str(value))

    def update_from_snapshot(self, s: Any) -> None:
        """Update all register displays from a VMStepSnapshot."""
        self._set("pc", s.pc)
        self._set("clock", s.clock)
        self._set("HALT", s.halt)
        self._set("PC_INTERRUPT", s.reg_PC_INTERRUPT)
        self._set("PC_INTERRUPT_A", s.reg_PC_INTERRUPT_A)
        self._set("X", s.reg_X)
        self._set("Y", s.reg_Y)
        self._set("RES", s.reg_RES)
        self._set("CRY", s.reg_CRY)
        self._set("SGN", s.reg_SGN)
        self._set("LOG", s.reg_LOG)
        self._set("PLAYER", s.reg_PLAYER)
        self._set("STN", s.reg_STN)
        self._set("WXY", s.reg_WXY)
        for i in range(8):
            self._set(f"X{i}", getattr(s, f"reg_X{i}"))
            self._set(f"Y{i}", getattr(s, f"reg_Y{i}"))
            self._set(f"GP{i}", getattr(s, f"reg_GP{i}"))
        # Memory table
        for addr, val in enumerate(s.memory_0_to_50):
            self._mem_table.setItem(addr, 0, QTableWidgetItem(str(addr)))
            self._mem_table.setItem(addr, 1, QTableWidgetItem(str(val)))
        # Stack
        self._stack_label.setText(str(s.stack_top_10) if s.stack_top_10 else "(empty)")
        # Board info
        for name, bi_snapshot in s.board_info.items():
            lbl = self._bi_labels.get(name)
            if lbl:
                count = len(bi_snapshot.values)
                ptr = bi_snapshot.ptr
                cur = bi_snapshot.current_value
                lbl.setText(f"ptr={ptr}, count={count}, cur={cur}")


class VMInspectorPanel(QWidget):
    """Panel for loading genomes and step-debugging them through the VM."""

    def __init__(self, app_state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._session: VMDebugSession | None = None
        self._current_dna: list[Any] = []
        self._step_count: int = 0
        self._population_lines: list[str] = []
        self._population_file: Path | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        # Top toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self._file_edit = QLabel("No file loaded")
        btn_browse = QPushButton("Browse Population File…")
        btn_browse.clicked.connect(self._on_browse_file)

        self._genome_spin = QSpinBox()
        self._genome_spin.setMinimum(0)
        self._genome_spin.setMaximum(0)
        self._genome_spin.setPrefix("Genome #")

        self._player_combo = QComboBox()
        self._player_combo.addItems(["black", "white"])

        btn_load = QPushButton("Load Genome")
        btn_load.clicked.connect(self._on_load_genome)

        toolbar_layout.addWidget(QLabel("File:"))
        toolbar_layout.addWidget(self._file_edit, 1)
        toolbar_layout.addWidget(btn_browse)
        toolbar_layout.addWidget(QLabel("Genome:"))
        toolbar_layout.addWidget(self._genome_spin)
        toolbar_layout.addWidget(QLabel("Player:"))
        toolbar_layout.addWidget(self._player_combo)
        toolbar_layout.addWidget(btn_load)
        outer.addWidget(toolbar)

        # Center 3-pane splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: genome listing
        self._genome_view = GenomeCodeView()
        splitter.addWidget(self._genome_view)

        # Middle: register panel
        self._register_panel = RegisterPanel()
        splitter.addWidget(self._register_panel)

        # Right: board
        self._board_widget = BoardWidget()
        splitter.addWidget(self._board_widget)

        splitter.setSizes([350, 350, 300])
        outer.addWidget(splitter, 1)

        # Bottom controls
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self._btn_step = QPushButton("Step [Space]")
        self._btn_run = QPushButton("Run [F5]")
        self._btn_pause = QPushButton("Pause")
        self._btn_reset = QPushButton("Reset")

        for btn in (self._btn_step, self._btn_run, self._btn_pause, self._btn_reset):
            btn.setEnabled(False)
            bottom_layout.addWidget(btn)

        bottom_layout.addWidget(QLabel("Speed:"))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setMinimum(0)
        self._speed_slider.setMaximum(500)
        self._speed_slider.setValue(0)
        self._speed_slider.setFixedWidth(150)
        bottom_layout.addWidget(self._speed_slider)

        self._step_counter_label = QLabel("Step: 0 / 4000")
        bottom_layout.addWidget(self._step_counter_label)
        bottom_layout.addStretch()

        outer.addWidget(bottom)

        # Connect buttons
        self._btn_step.clicked.connect(self._on_step)
        self._btn_run.clicked.connect(self._on_run)
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_reset.clicked.connect(self._on_reset)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Space"), self, self._on_step)
        QShortcut(QKeySequence("F5"), self, self._on_run)

    def _on_browse_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Population File",
            str(Path.home()),
            "Population files (*.py *.pop);;All files (*)",
        )
        if not path_str:
            return
        self._population_file = Path(path_str)
        try:
            raw = self._population_file.read_text(encoding="utf-8").splitlines()
            self._population_lines = [
                line.strip().split("<<<>>>")[0].strip()
                for line in raw
                if line.strip() and not line.startswith("#")
            ]
            self._file_edit.setText(str(self._population_file))
            count = len(self._population_lines)
            self._genome_spin.setMaximum(max(0, count - 1))
            logger.debug("Loaded population file with %d genomes", count)
        except OSError as exc:
            logger.error("Cannot read population file: %s", exc)

    def _on_load_genome(self) -> None:
        idx = self._genome_spin.value()
        if not self._population_lines or idx >= len(self._population_lines):
            return
        raw_repr = self._population_lines[idx]
        try:
            dna = ast.literal_eval(raw_repr)
        except (SyntaxError, ValueError) as exc:
            logger.error("Failed to parse genome at index %d: %s", idx, exc)
            return

        player = self._player_combo.currentText()
        board: dict = {}  # empty board for now

        # Create a new session
        if self._session is not None:
            self._session.stop_thread()
        self._session = VMDebugSession(parent=self)
        self._session.snapshot_ready.connect(self._on_snapshot)
        self._session.execution_finished.connect(self._on_execution_finished)
        self._session.paused.connect(self._on_snapshot)

        self._current_dna = dna
        self._step_count = 0
        self._genome_view.load_genome(dna)
        self._session.load(dna, board, player)

        for btn in (self._btn_step, self._btn_run, self._btn_pause, self._btn_reset):
            btn.setEnabled(True)
        self._step_counter_label.setText("Step: 0 / 4000")
        logger.debug("Loaded genome #%d (%d instructions)", idx, len(dna))

    @Slot(object)
    def _on_snapshot(self, snapshot: Any) -> None:
        self._step_count = snapshot.clock
        self._step_counter_label.setText(f"Step: {snapshot.clock} / 4000")
        self._register_panel.update_from_snapshot(snapshot)
        self._genome_view.highlight_pc(snapshot.pc)
        self._board_widget.update_from_snapshot(snapshot)

    @Slot(object)
    def _on_execution_finished(self, snapshot: Any) -> None:
        self._on_snapshot(snapshot)
        logger.debug(
            "VM execution finished. Final move: X=%d Y=%d",
            snapshot.move_x,
            snapshot.move_y,
        )
        self._btn_run.setEnabled(False)
        self._btn_step.setEnabled(False)

    def _on_step(self) -> None:
        if self._session:
            self._session.step()

    def _on_run(self) -> None:
        if self._session:
            self._session.run()

    def _on_pause(self) -> None:
        if self._session:
            self._session.pause()

    def _on_reset(self) -> None:
        if self._session:
            self._step_count = 0
            self._session.reset()
            self._btn_run.setEnabled(True)
            self._btn_step.setEnabled(True)
            self._genome_view.highlight_pc(-1)

    def _on_speed_changed(self, value: int) -> None:
        if self._session:
            self._session.set_step_delay(value)

    def load_dna(self, dna: list[Any], player: str = "black") -> None:
        """Programmatically load a genome DNA list (called from other panels)."""
        self._current_dna = dna
        self._genome_view.load_genome(dna)
        if self._session is not None:
            self._session.stop_thread()
        self._session = VMDebugSession(parent=self)
        self._session.snapshot_ready.connect(self._on_snapshot)
        self._session.execution_finished.connect(self._on_execution_finished)
        self._session.paused.connect(self._on_snapshot)
        self._session.load(dna, {}, player)
        for btn in (self._btn_step, self._btn_run, self._btn_pause, self._btn_reset):
            btn.setEnabled(True)
