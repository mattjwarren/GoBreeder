from __future__ import annotations

import datetime
import logging
import subprocess
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GoBreeder.gui.dialogs.new_deployment_dialog import NewDeploymentDialog
from GoBreeder.gui.models.app_state import AppState
from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.deployment_factory import DeploymentError, DeploymentFactory
from GoBreeder.gui.models.deployment_manager import DeploymentManager, DeploymentManagerError
from GoBreeder.gui.models.population_library import PopulationLibrary, PopulationLibraryError

logger = logging.getLogger(__name__)


class DeploymentPanel(QWidget):
    """Panel for creating, viewing, and managing deployments."""

    go_to_run_requested = Signal(str)  # emits deployment name

    def __init__(
        self,
        app_state: AppState,
        library: PopulationLibrary | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._library = library
        self._manager = DeploymentManager()
        self._factory = DeploymentFactory()
        self._selected_deployment: DeploymentModel | None = None
        self._build_ui()
        app_state.deployments_changed.connect(self._refresh_list)
        self._refresh_list()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left: list + toolbar
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Toolbar above list
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self._btn_new = QPushButton("New Deployment")
        self._btn_delete = QPushButton("Delete")
        self._btn_open_dir = QPushButton("Open Directory")
        self._btn_delete.setEnabled(False)
        self._btn_open_dir.setEnabled(False)

        toolbar_layout.addWidget(self._btn_new)
        toolbar_layout.addWidget(self._btn_delete)
        toolbar_layout.addWidget(self._btn_open_dir)
        toolbar_layout.addStretch()

        self._list = QListWidget()
        left_layout.addWidget(toolbar)
        left_layout.addWidget(self._list)

        # Right: detail pane
        self._detail_widget = QGroupBox("Deployment Details")
        detail_layout = QFormLayout(self._detail_widget)

        self._detail_name = QLineEdit()
        self._detail_name.setReadOnly(True)
        self._detail_dir = QLineEdit()
        self._detail_dir.setReadOnly(True)
        self._detail_pop_status = QLabel("—")
        self._detail_run_state = QLabel("—")
        self._btn_go_to_run = QPushButton("Go to Breeding Run")
        self._btn_go_to_run.setEnabled(False)
        self._btn_refresh_code = QPushButton("Refresh Code")
        self._btn_refresh_code.setEnabled(False)
        self._btn_refresh_code.setToolTip(
            "Re-copy source code files into this deployment.\n"
            "Population data and config are not affected."
        )
        self._btn_inject_population = QPushButton("Inject Population from Library…")
        self._btn_inject_population.setEnabled(False)

        detail_layout.addRow("Name:", self._detail_name)
        detail_layout.addRow("Directory:", self._detail_dir)
        detail_layout.addRow("Population:", self._detail_pop_status)
        detail_layout.addRow("Run State:", self._detail_run_state)
        detail_layout.addRow("", self._btn_go_to_run)
        detail_layout.addRow("", self._btn_refresh_code)
        detail_layout.addRow("", self._btn_inject_population)

        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(self._detail_widget, 2)

        # Connections
        self._list.currentRowChanged.connect(self._on_selection_changed)
        self._btn_new.clicked.connect(self._on_new_deployment)
        self._btn_delete.clicked.connect(self._on_delete_deployment)
        self._btn_open_dir.clicked.connect(self._on_open_directory)
        self._btn_go_to_run.clicked.connect(self._on_go_to_run)
        self._btn_refresh_code.clicked.connect(self._on_refresh_code)
        self._btn_inject_population.clicked.connect(self._on_inject_population)

    def _refresh_list(self) -> None:
        self._list.clear()
        for deployment in self._app_state.deployments:
            state_badge = f"[{deployment.run_state.value}]"
            item = QListWidgetItem(f"{deployment.name}  {state_badge}")
            item.setData(Qt.ItemDataRole.UserRole, deployment.name)
            self._list.addItem(item)
        self._update_detail()

    def _on_selection_changed(self, row: int) -> None:
        if row < 0:
            self._selected_deployment = None
        else:
            name = self._list.item(row).data(Qt.ItemDataRole.UserRole)
            self._selected_deployment = next(
                (d for d in self._app_state.deployments if d.name == name), None
            )
        self._update_detail()

    def _update_detail(self) -> None:
        d = self._selected_deployment
        if d is None:
            self._detail_name.clear()
            self._detail_dir.clear()
            self._detail_pop_status.setText("—")
            self._detail_run_state.setText("—")
            self._btn_delete.setEnabled(False)
            self._btn_open_dir.setEnabled(False)
            self._btn_go_to_run.setEnabled(False)
            self._btn_refresh_code.setEnabled(False)
            return

        self._detail_name.setText(d.name)
        self._detail_dir.setText(str(d.deployment_dir))
        self._detail_run_state.setText(d.run_state.value)
        self._btn_delete.setEnabled(not d.is_running())
        self._btn_open_dir.setEnabled(True)
        self._btn_go_to_run.setEnabled(True)
        self._btn_refresh_code.setEnabled(not d.is_running())
        self._btn_inject_population.setEnabled(
            self._library is not None and not d.is_running()
        )

        # Population file status
        pop_path = d.population_file_path()
        if pop_path.exists():
            try:
                count = sum(
                    1
                    for line in pop_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
                mtime = datetime.datetime.fromtimestamp(pop_path.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
                self._detail_pop_status.setText(f"{count} lines  (modified {mtime})")
            except OSError:
                self._detail_pop_status.setText("exists (unreadable)")
        else:
            self._detail_pop_status.setText("not found")

    def _on_new_deployment(self) -> None:
        dlg = NewDeploymentDialog(self)
        if dlg.exec():
            name, parent_dir = dlg.get_result()
            try:
                deployment = self._factory.create(name=name, parent_dir=parent_dir)
                self._app_state.add_deployment(deployment)
            except DeploymentError as exc:
                QMessageBox.critical(self, "Create Deployment Failed", str(exc))

    def _on_delete_deployment(self) -> None:
        if self._selected_deployment is None:
            return
        d = self._selected_deployment
        reply = QMessageBox.question(
            self,
            "Delete Deployment",
            f"Delete deployment '{d.name}' and its directory?\n\n{d.deployment_dir}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._manager.delete(d)
            self._app_state.remove_deployment(d)
        except DeploymentManagerError as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))

    def _on_open_directory(self) -> None:
        if self._selected_deployment is None:
            return
        path = self._selected_deployment.deployment_dir
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _on_go_to_run(self) -> None:
        if self._selected_deployment is not None:
            self.go_to_run_requested.emit(self._selected_deployment.name)

    def _on_refresh_code(self) -> None:
        if self._selected_deployment is None:
            return
        d = self._selected_deployment
        reply = QMessageBox.question(
            self,
            "Refresh Code",
            f"Re-copy source code files into '{d.name}'?\n\n"
            "Population data, config.py, and stats will not be changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            updated = self._factory.refresh_code(d)
            QMessageBox.information(
                self,
                "Refresh Complete",
                f"Updated {len(updated)} file(s):\n" + "\n".join(f"  {f}" for f in updated),
            )
            logger.info("Refreshed code for deployment %r: %s", d.name, updated)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Refresh Failed", str(exc))

    def _on_inject_population(self) -> None:
        if self._selected_deployment is None or self._library is None:
            return
        records = self._library.list_all()
        if not records:
            QMessageBox.information(self, "Empty Library", "No populations in library.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Choose Population")
        vlayout = QVBoxLayout(dlg)
        vlayout.addWidget(QLabel("Select a population to inject:"))
        pop_list = QListWidget()
        for rec in records:
            pop_list.addItem(f"{rec.name}  ({rec.genome_count} genomes)")
        vlayout.addWidget(pop_list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        vlayout.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if pop_list.currentRow() < 0:
            return
        record = records[pop_list.currentRow()]
        reply = QMessageBox.warning(
            self, "Confirm Injection",
            f"Overwrite population for '{self._selected_deployment.name}' with '{record.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._library.inject_into_deployment(record, self._selected_deployment)
            QMessageBox.information(self, "Injected", f"Population '{record.name}' injected.")
            logger.info(
                "Injected population %r into deployment %r",
                record.name, self._selected_deployment.name,
            )
        except (PopulationLibraryError, OSError) as exc:
            QMessageBox.critical(self, "Injection Failed", str(exc))
