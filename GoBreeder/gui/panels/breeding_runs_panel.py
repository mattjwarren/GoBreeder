from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from GoBreeder.gui.models.app_state import AppState
from GoBreeder.gui.models.breeding_run_controller import BreedingRunController
from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.run_registry import RunRegistry
from GoBreeder.gui.models.run_state import RunState

logger = logging.getLogger(__name__)

MAX_LOG_LINES = 5000


class BreedingRunsPanel(QWidget):
    """Panel for starting, stopping, and monitoring breeding runs."""

    def __init__(
        self,
        app_state: AppState,
        run_registry: RunRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._run_registry = run_registry
        self._selected_name: str | None = None
        self._log_buffers: dict[str, list[str]] = {}
        self._generation_counters: dict[str, int] = {}
        self._build_ui()
        app_state.deployments_changed.connect(self._refresh_list)
        run_registry.run_state_changed.connect(self._on_run_state_changed)
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: deployment list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Deployments"))
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list)
        splitter.addWidget(left)

        # Right: run detail pane
        right = QWidget()
        right_layout = QVBoxLayout(right)

        # Start/Stop controls
        ctrl_row = QWidget()
        ctrl_layout = QHBoxLayout(ctrl_row)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_start_stop = QPushButton("Start Run")
        self._btn_start_stop.setEnabled(False)
        self._generation_label = QLabel("Generation: —")
        ctrl_layout.addWidget(self._btn_start_stop)
        ctrl_layout.addWidget(self._generation_label)
        ctrl_layout.addStretch()
        right_layout.addWidget(ctrl_row)

        # Log viewer
        right_layout.addWidget(QLabel("Run Log:"))
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(MAX_LOG_LINES)
        font = self._log_view.font()
        font.setFamily("Consolas")
        self._log_view.setFont(font)
        right_layout.addWidget(self._log_view)

        splitter.addWidget(right)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

        self._btn_start_stop.clicked.connect(self._on_start_stop)

    def _refresh_list(self) -> None:
        self._list.clear()
        for deployment in self._app_state.deployments:
            gen = self._generation_counters.get(deployment.name, 0)
            state_badge = deployment.run_state.value
            text = f"{deployment.name}  [{state_badge}]  gen {gen}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, deployment.name)
            self._list.addItem(item)
        self._update_detail()

    def _get_selected_deployment(self) -> DeploymentModel | None:
        if self._selected_name is None:
            return None
        return next((d for d in self._app_state.deployments if d.name == self._selected_name), None)

    def _on_selection_changed(self, row: int) -> None:
        if row >= 0:
            item = self._list.item(row)
            if item:
                self._selected_name = item.data(Qt.ItemDataRole.UserRole)
        else:
            self._selected_name = None
        self._update_detail()
        self._load_log_for_selected()

    def _update_detail(self) -> None:
        d = self._get_selected_deployment()
        if d is None:
            self._btn_start_stop.setEnabled(False)
            self._btn_start_stop.setText("Start Run")
            self._generation_label.setText("Generation: —")
            return

        is_running = d.run_state == RunState.RUNNING
        is_stopping = d.run_state == RunState.STOPPING

        if is_running:
            self._btn_start_stop.setText("Stop Run")
            self._btn_start_stop.setEnabled(True)
        elif is_stopping:
            self._btn_start_stop.setText("Stopping…")
            self._btn_start_stop.setEnabled(False)
        else:
            self._btn_start_stop.setText("Start Run")
            self._btn_start_stop.setEnabled(True)

        gen = self._generation_counters.get(d.name, 0)
        self._generation_label.setText(f"Generation: {gen}")

    def _load_log_for_selected(self) -> None:
        self._log_view.clear()
        if self._selected_name and self._selected_name in self._log_buffers:
            self._log_view.setPlainText("\n".join(self._log_buffers[self._selected_name]))

    def _on_start_stop(self) -> None:
        d = self._get_selected_deployment()
        if d is None:
            return
        if d.run_state == RunState.RUNNING:
            self._run_registry.stop(d, self._app_state)
        else:
            self._log_buffers.setdefault(d.name, [])
            self._run_registry.start(d, self._app_state)
            ctrl = self._run_registry.controller_for(d.name)
            if ctrl is not None and isinstance(ctrl, BreedingRunController):
                ctrl.log_line_received.connect(
                    lambda line, name=d.name: self._on_log_line(name, line)
                )
                ctrl.generation_advanced.connect(
                    lambda gen, name=d.name: self._on_generation(name, gen)
                )

    def _on_log_line(self, deployment_name: str, line: str) -> None:
        buf = self._log_buffers.setdefault(deployment_name, [])
        buf.append(line)
        if len(buf) > MAX_LOG_LINES:
            del buf[:-MAX_LOG_LINES]
        if deployment_name == self._selected_name:
            self._log_view.appendPlainText(line)

    def _on_generation(self, deployment_name: str, generation: int) -> None:
        self._generation_counters[deployment_name] = generation
        self._refresh_list()
        if deployment_name == self._selected_name:
            self._generation_label.setText(f"Generation: {generation}")

    @Slot(str, str)
    def _on_run_state_changed(self, deployment_name: str, new_state: str) -> None:
        self._refresh_list()
        if deployment_name == self._selected_name:
            self._update_detail()

    def select_deployment(self, name: str) -> None:
        """Programmatically select a deployment by name (called from other panels)."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                self._list.setCurrentRow(i)
                return
