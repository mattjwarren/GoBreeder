from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GoBreeder.gui.archive.population_file_reader import read_population_file
from GoBreeder.gui.models.app_state import AppState
from GoBreeder.gui.models.population_library import PopulationLibrary, PopulationLibraryError, PopulationRecord

logger = logging.getLogger(__name__)


class PopulationLibraryPanel(QWidget):
    """Panel for managing the population library."""

    open_in_inspector_requested = Signal(list)  # dna list

    def __init__(
        self,
        app_state: AppState,
        library: PopulationLibrary,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._library = library
        self._selected_record: PopulationRecord | None = None
        self._build_ui()
        library.library_changed.connect(self._refresh_list)
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        # Left pane: list + toolbar
        left = QWidget()
        left_layout = QVBoxLayout(left)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_new = QPushButton("New")
        self._btn_import = QPushButton("Import from File…")
        self._btn_delete = QPushButton("Delete")
        self._btn_rename = QPushButton("Rename")
        self._btn_import_sel = QPushButton("Import from Archive Selection")
        self._btn_import_sel.setEnabled(False)  # enabled externally

        for btn in (self._btn_new, self._btn_import, self._btn_delete, self._btn_rename):
            toolbar_layout.addWidget(btn)
        toolbar_layout.addStretch()
        left_layout.addWidget(toolbar)
        left_layout.addWidget(self._btn_import_sel)

        self._library_list = QListWidget()
        left_layout.addWidget(self._library_list)
        splitter.addWidget(left)

        # Right pane: detail
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self._detail_name = QLabel("—")
        self._detail_path = QLabel("—")
        self._detail_path.setWordWrap(True)
        self._detail_count = QLabel("—")
        right_layout.addWidget(QLabel("Name:"))
        right_layout.addWidget(self._detail_name)
        right_layout.addWidget(QLabel("Path:"))
        right_layout.addWidget(self._detail_path)
        right_layout.addWidget(QLabel("Genome count:"))
        right_layout.addWidget(self._detail_count)

        right_layout.addWidget(QLabel("Notes:"))
        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setMaximumHeight(80)
        right_layout.addWidget(self._notes_edit)

        right_layout.addWidget(QLabel("Preview (first 20 genomes):"))
        self._preview_table = QTableWidget(0, 2)
        self._preview_table.setHorizontalHeaderLabels(["Index", "Length"])
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.setMaximumHeight(200)
        right_layout.addWidget(self._preview_table)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_inject = QPushButton("Inject into Deployment…")
        self._btn_inspect = QPushButton("Open in VM Inspector")
        btn_layout.addWidget(self._btn_inject)
        btn_layout.addWidget(self._btn_inspect)
        btn_layout.addStretch()
        right_layout.addWidget(btn_row)
        right_layout.addStretch()
        splitter.addWidget(right)

        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

        # Connections
        self._library_list.currentRowChanged.connect(self._on_selection_changed)
        self._btn_new.clicked.connect(self._on_new)
        self._btn_import.clicked.connect(self._on_import)
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_rename.clicked.connect(self._on_rename)
        self._btn_inject.clicked.connect(self._on_inject)
        self._btn_inspect.clicked.connect(self._on_inspect)

    def _refresh_list(self) -> None:
        self._library_list.clear()
        for rec in self._library.list_all():
            text = f"{rec.name}  ({rec.genome_count} genomes, {rec.modified_at.strftime('%Y-%m-%d')})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, rec.name)
            self._library_list.addItem(item)
        self._update_detail()

    def _on_selection_changed(self, row: int) -> None:
        if row < 0:
            self._selected_record = None
        else:
            item = self._library_list.item(row)
            if item:
                name = item.data(Qt.ItemDataRole.UserRole)
                self._selected_record = next(
                    (r for r in self._library.list_all() if r.name == name), None
                )
        self._update_detail()

    def _update_detail(self) -> None:
        rec = self._selected_record
        if rec is None:
            self._detail_name.setText("—")
            self._detail_path.setText("—")
            self._detail_count.setText("—")
            self._notes_edit.setPlainText("")
            self._preview_table.setRowCount(0)
            return
        self._detail_name.setText(rec.name)
        self._detail_path.setText(str(rec.file_path))
        self._detail_count.setText(str(rec.genome_count))
        self._notes_edit.setPlainText(rec.notes)
        try:
            genomes = read_population_file(rec.file_path)[:20]
        except Exception:
            genomes = []
        self._preview_table.setRowCount(len(genomes))
        for i, g in enumerate(genomes):
            self._preview_table.setItem(i, 0, QTableWidgetItem(str(i)))
            self._preview_table.setItem(i, 1, QTableWidgetItem(str(g.instruction_count)))

    def _on_new(self) -> None:
        name, ok = QInputDialog.getText(self, "New Population", "Population name:")
        if not ok or not name.strip():
            return
        try:
            self._library.add(name.strip())
        except PopulationLibraryError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _on_import(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Import Population File", str(Path.home()),
            "Population files (*.py *.pop);;All files (*)"
        )
        if not path_str:
            return
        name, ok = QInputDialog.getText(self, "Population Name", "Name for this population:")
        if not ok or not name.strip():
            return
        try:
            self._library.add(name.strip(), source_path=Path(path_str))
        except PopulationLibraryError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _on_delete(self) -> None:
        if self._selected_record is None:
            return
        reply = QMessageBox.question(
            self, "Delete Population",
            f"Delete '{self._selected_record.name}' from library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._library.delete(self._selected_record)
            self._selected_record = None

    def _on_rename(self) -> None:
        if self._selected_record is None:
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename Population",
            f"New name for '{self._selected_record.name}':",
            text=self._selected_record.name,
        )
        if not ok or not new_name.strip():
            return
        try:
            self._library.rename(self._selected_record, new_name.strip())
        except PopulationLibraryError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _on_inject(self) -> None:
        if self._selected_record is None:
            return
        idle_deployments = [d for d in self._app_state.deployments if not d.is_running()]
        if not idle_deployments:
            QMessageBox.warning(self, "No IDLE Deployments", "There are no IDLE deployments to inject into.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Choose Deployment")
        vlayout = QVBoxLayout(dlg)
        vlayout.addWidget(QLabel("Select target deployment:"))
        dep_list = QListWidget()
        for d in idle_deployments:
            dep_list.addItem(d.name)
        vlayout.addWidget(dep_list)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        vlayout.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dep_list.currentRow() < 0:
            return
        target_name = dep_list.currentItem().text()
        target = next((d for d in idle_deployments if d.name == target_name), None)
        if target is None:
            return
        reply = QMessageBox.warning(
            self, "Confirm Injection",
            f"This will overwrite the current population for '{target.name}'. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._library.inject_into_deployment(self._selected_record, target)
            QMessageBox.information(self, "Injected", f"Population injected into '{target.name}'.")
        except (PopulationLibraryError, OSError) as exc:
            QMessageBox.critical(self, "Injection Failed", str(exc))

    def _on_inspect(self) -> None:
        if self._selected_record is None:
            return
        try:
            genomes = read_population_file(self._selected_record.file_path)
            if not genomes:
                QMessageBox.information(self, "Empty", "This population has no genomes.")
                return
            g = genomes[0]
            self.open_in_inspector_requested.emit(g.dna)
            logger.debug("Emitted open_in_inspector_requested for genome from %r", self._selected_record.name)
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def import_from_selection(self, dna_reprs: list[str]) -> None:
        """Called externally to import selected genomes from archive browser."""
        name, ok = QInputDialog.getText(self, "Import from Archive", "Name for this population:")
        if not ok or not name.strip():
            return
        try:
            self._library.add_from_dna_list(name.strip(), dna_reprs)
        except PopulationLibraryError as exc:
            QMessageBox.warning(self, "Error", str(exc))
