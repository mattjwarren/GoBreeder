from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

logger = logging.getLogger(__name__)

BOARD_SIZE = 9
CELL_SIZE = 50
MARGIN = 30


class BoardWidget(QWidget):
    """Renders a 9x9 Go board with stones and VM cursor markers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(
            BOARD_SIZE * CELL_SIZE + 2 * MARGIN,
            BOARD_SIZE * CELL_SIZE + 2 * MARGIN,
        )
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self._board: dict[tuple[int, int], int] = {}  # {(x,y): -1 (black) | 0 | 1 (white)}
        self._move_candidate: tuple[int, int] | None = None  # (reg_X % 9, reg_Y % 9)
        self._stn_cursor: tuple[int, int] | None = None       # reg_STN

    def set_board(self, board: dict[tuple[int, int], int]) -> None:
        self._board = board
        self.update()

    def set_move_candidate(self, x: int, y: int) -> None:
        self._move_candidate = (x % BOARD_SIZE, y % BOARD_SIZE)
        self.update()

    def set_stn_cursor(self, stn: tuple[int, int]) -> None:
        self._stn_cursor = stn
        self.update()

    def update_from_snapshot(self, snapshot: Any) -> None:
        """Update the board from a VMStepSnapshot."""
        parsed_board: dict[tuple[int, int], int] = {}
        for k, v in snapshot.board.items():
            try:
                coords = tuple(int(x) for x in k.strip("()").split(","))
                if len(coords) == 2:
                    parsed_board[(coords[0], coords[1])] = v
            except (ValueError, AttributeError):
                pass
        self._board = parsed_board
        self._move_candidate = (snapshot.reg_X % BOARD_SIZE, snapshot.reg_Y % BOARD_SIZE)
        stn = snapshot.reg_STN
        self._stn_cursor = (
            (stn[0], stn[1])
            if isinstance(stn, (tuple, list)) and len(stn) == 2
            else None
        )
        self.update()

    def _cell_to_pixel(self, x: int, y: int) -> QPointF:
        px = MARGIN + x * CELL_SIZE + CELL_SIZE // 2
        py = MARGIN + y * CELL_SIZE + CELL_SIZE // 2
        return QPointF(px, py)

    def paintEvent(self, event: Any) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(219, 178, 112))  # wood colour

        # Grid lines
        pen = QPen(QColor(0, 0, 0), 1)
        painter.setPen(pen)
        for i in range(BOARD_SIZE):
            start = self._cell_to_pixel(i, 0)
            end = self._cell_to_pixel(i, BOARD_SIZE - 1)
            painter.drawLine(start, end)
            start = self._cell_to_pixel(0, i)
            end = self._cell_to_pixel(BOARD_SIZE - 1, i)
            painter.drawLine(start, end)

        # Star points (9x9 board)
        star_points = [(2, 2), (6, 2), (2, 6), (6, 6), (4, 4)]
        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.setPen(Qt.PenStyle.NoPen)
        for sx, sy in star_points:
            c = self._cell_to_pixel(sx, sy)
            painter.drawEllipse(c, 3.5, 3.5)

        # STN cursor (faint blue square)
        if self._stn_cursor is not None:
            sx, sy = self._stn_cursor[0] % BOARD_SIZE, self._stn_cursor[1] % BOARD_SIZE
            c = self._cell_to_pixel(sx, sy)
            painter.setPen(QPen(QColor(0, 80, 200, 160), 2))
            painter.setBrush(QBrush(QColor(0, 80, 200, 40)))
            half = CELL_SIZE // 2 - 4
            painter.drawRect(QRectF(c.x() - half, c.y() - half, half * 2, half * 2))

        # Move candidate (yellow circle)
        if self._move_candidate is not None:
            mx, my = self._move_candidate
            c = self._cell_to_pixel(mx, my)
            painter.setPen(QPen(QColor(255, 200, 0, 200), 3))
            painter.setBrush(QBrush(QColor(255, 220, 0, 80)))
            r = CELL_SIZE // 2 - 6
            painter.drawEllipse(c, r, r)

        # Stones
        radius = CELL_SIZE // 2 - 4
        for (x, y), val in self._board.items():
            if x < 0 or x >= BOARD_SIZE or y < 0 or y >= BOARD_SIZE:
                continue
            c = self._cell_to_pixel(x, y)
            if val == -1:  # black
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(20, 20, 20)))
            elif val == 1:  # white
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                painter.setBrush(QBrush(QColor(240, 240, 240)))
            else:
                continue
            painter.drawEllipse(c, radius, radius)

        painter.end()
