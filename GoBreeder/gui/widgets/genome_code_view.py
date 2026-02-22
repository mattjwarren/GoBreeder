from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QWidget

logger = logging.getLogger(__name__)


class GenomeCodeView(QTableWidget):
    """Displays a genome's instruction listing and highlights the current PC."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["Index", "Opcode", "Operand A", "Operand B"])
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        font = QFont("Consolas", 10)
        self.setFont(font)
        self._current_pc: int = -1

    def load_genome(self, dna: list[Any]) -> None:
        """Load a genome (list of (opcode, [op1, op2]) tuples)."""
        self.setRowCount(len(dna))
        for i, instr in enumerate(dna):
            opcode = instr[0] if len(instr) > 0 else ""
            operands = instr[1] if len(instr) > 1 else []
            op_a = str(operands[0]) if operands and len(operands) > 0 else ""
            op_b = str(operands[1]) if operands and len(operands) > 1 else ""
            self.setItem(i, 0, QTableWidgetItem(str(i)))
            self.setItem(i, 1, QTableWidgetItem(str(opcode)))
            self.setItem(i, 2, QTableWidgetItem(op_a))
            self.setItem(i, 3, QTableWidgetItem(op_b))
        self._current_pc = -1
        self.resizeColumnsToContents()

    def highlight_pc(self, pc: int) -> None:
        """Highlight the row at pc and scroll to it."""
        # Clear previous highlight
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(QColor(Qt.GlobalColor.transparent))

        self._current_pc = pc
        if 0 <= pc < self.rowCount():
            highlight_color = QColor(255, 255, 120)  # yellow
            for col in range(self.columnCount()):
                item = self.item(pc, col)
                if item:
                    item.setBackground(highlight_color)
            self.scrollToItem(self.item(pc, 0), QTableWidget.ScrollHint.PositionAtCenter)
