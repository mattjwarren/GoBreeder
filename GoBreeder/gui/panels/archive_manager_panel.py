from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GoBreeder.gui.archive.archive_reader import ArchiveEntry, ArchiveReader
from GoBreeder.gui.archive.population_file_reader import GenomeEntry, read_population_from_archive
from GoBreeder.gui.models.app_state import AppState
from GoBreeder.gui.models.population_library import PopulationLibrary
from GoBreeder.gui.panels.population_library_panel import PopulationLibraryPanel

logger = logging.getLogger(__name__)


class ArchiveBrowserWidget(QWidget):
    """Widget for browsing tar archives and viewing/exporting population files."""

    view_genome_requested = Signal(list)  # emitted with DNA list
    import_to_library_requested = Signal(list)  # emitted with list of dna_repr strings

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reader = ArchiveReader()
        self._archives: list[Path] = []
        self._archive_entries: dict[str, list[ArchiveEntry]] = {}  # archive path str -> entries
        self._selected_archive: Path | None = None
        self._show_pop_only: bool = False
        self._current_genomes: list[GenomeEntry] = []
        self._export_genomes: list[GenomeEntry] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left pane: archives list + tree ----
        left = QWidget()
        left_layout = QVBoxLayout(left)

        archive_toolbar = QWidget()
        archive_toolbar_layout = QHBoxLayout(archive_toolbar)
        archive_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_add_archive = QPushButton("Add Archive…")
        self._btn_remove_archive = QPushButton("Remove")
        self._btn_remove_archive.setEnabled(False)
        archive_toolbar_layout.addWidget(self._btn_add_archive)
        archive_toolbar_layout.addWidget(self._btn_remove_archive)
        archive_toolbar_layout.addStretch()
        left_layout.addWidget(archive_toolbar)

        self._archive_list = QListWidget()
        self._archive_list.setMaximumHeight(120)
        left_layout.addWidget(QLabel("Archives:"))
        left_layout.addWidget(self._archive_list)

        self._btn_pop_filter = QPushButton("Show population files only")
        self._btn_pop_filter.setCheckable(True)
        left_layout.addWidget(self._btn_pop_filter)

        left_layout.addWidget(QLabel("Files:"))
        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Archive contents")
        self._tree.setColumnCount(1)
        left_layout.addWidget(self._tree)

        splitter.addWidget(left)

        # ---- Middle pane: genome table ----
        middle = QWidget()
        middle_layout = QVBoxLayout(middle)

        self._current_file_label = QLabel("No file selected")
        self._current_file_label.setWordWrap(True)
        middle_layout.addWidget(self._current_file_label)

        self._genome_table = QTableWidget(0, 4)
        self._genome_table.setHorizontalHeaderLabels(["Index", "Length", "Fitness", "Preview"])
        self._genome_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._genome_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        middle_layout.addWidget(self._genome_table)

        middle_btns = QWidget()
        middle_btns_layout = QHBoxLayout(middle_btns)
        middle_btns_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_view_inspector = QPushButton("View in VM Inspector")
        self._btn_add_to_selection = QPushButton("Add to Selection")
        middle_btns_layout.addWidget(self._btn_view_inspector)
        middle_btns_layout.addWidget(self._btn_add_to_selection)
        middle_btns_layout.addStretch()
        middle_layout.addWidget(middle_btns)

        splitter.addWidget(middle)

        # ---- Right pane: export selection ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Export selection:"))

        self._export_list = QListWidget()
        right_layout.addWidget(self._export_list)

        right_btns = QWidget()
        right_btns_layout = QVBoxLayout(right_btns)
        right_btns_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_remove_export = QPushButton("Remove")
        self._btn_clear_export = QPushButton("Clear All")
        self._btn_save_population = QPushButton("Save as Population File…")
        self._btn_import_to_library = QPushButton("Import to Library")
        for btn in (self._btn_remove_export, self._btn_clear_export,
                    self._btn_save_population, self._btn_import_to_library):
            right_btns_layout.addWidget(btn)
        right_btns_layout.addStretch()
        right_layout.addWidget(right_btns)

        splitter.addWidget(right)
        splitter.setSizes([250, 450, 250])
        layout.addWidget(splitter)

        # Connections
        self._btn_add_archive.clicked.connect(self._on_add_archive)
        self._btn_remove_archive.clicked.connect(self._on_remove_archive)
        self._archive_list.currentRowChanged.connect(self._on_archive_selection_changed)
        self._btn_pop_filter.toggled.connect(self._on_toggle_pop_filter)
        self._tree.currentItemChanged.connect(self._on_tree_item_selected)
        self._btn_view_inspector.clicked.connect(self._on_view_in_inspector)
        self._btn_add_to_selection.clicked.connect(self._on_add_to_selection)
        self._btn_remove_export.clicked.connect(self._on_remove_from_export)
        self._btn_clear_export.clicked.connect(self._on_clear_export)
        self._btn_save_population.clicked.connect(self._on_save_population)
        self._btn_import_to_library.clicked.connect(self._on_import_to_library)

    # ------------------------------------------------------------------ archive list

    def _on_add_archive(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Archive", str(Path.home()),
            "Archives (*.tar *.tar.gz *.tar.bz2 *.tgz);;All files (*)"
        )
        if not path_str:
            return
        archive_path = Path(path_str)
        if archive_path in self._archives:
            QMessageBox.information(self, "Already loaded", f"{archive_path.name} is already loaded.")
            return
        try:
            entries = self._reader.list_files(archive_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error reading archive", str(exc))
            logger.warning("Failed to read archive %s: %s", archive_path, exc)
            return
        self._archives.append(archive_path)
        self._archive_entries[str(archive_path)] = entries
        item = QListWidgetItem(archive_path.name)
        item.setData(Qt.ItemDataRole.UserRole, str(archive_path))
        self._archive_list.addItem(item)
        logger.debug("Loaded archive %s with %d entries", archive_path, len(entries))

    def _on_remove_archive(self) -> None:
        row = self._archive_list.currentRow()
        if row < 0:
            return
        item = self._archive_list.takeItem(row)
        if item:
            archive_str = item.data(Qt.ItemDataRole.UserRole)
            archive_path = Path(archive_str)
            if archive_path in self._archives:
                self._archives.remove(archive_path)
            self._archive_entries.pop(archive_str, None)
            if self._selected_archive == archive_path:
                self._selected_archive = None
                self._tree.clear()
                self._current_file_label.setText("No file selected")
                self._current_genomes = []
                self._genome_table.setRowCount(0)
        self._btn_remove_archive.setEnabled(self._archive_list.count() > 0)

    def _on_archive_selection_changed(self, row: int) -> None:
        if row < 0:
            self._selected_archive = None
            self._btn_remove_archive.setEnabled(False)
            self._tree.clear()
            return
        item = self._archive_list.item(row)
        if item:
            self._selected_archive = Path(item.data(Qt.ItemDataRole.UserRole))
            self._btn_remove_archive.setEnabled(True)
            self._refresh_tree()

    def _on_toggle_pop_filter(self, checked: bool) -> None:
        self._show_pop_only = checked
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self._tree.clear()
        if self._selected_archive is None:
            return
        entries = self._archive_entries.get(str(self._selected_archive), [])
        if self._show_pop_only:
            entries = [e for e in entries if e.is_population_file()]

        # Build a directory tree
        node_map: dict[str, QTreeWidgetItem] = {}

        def get_or_create_dir(parts: tuple[str, ...]) -> QTreeWidgetItem:
            key = "/".join(parts)
            if key in node_map:
                return node_map[key]
            if len(parts) == 1:
                node = QTreeWidgetItem(self._tree, [parts[0]])
                node.setData(0, Qt.ItemDataRole.UserRole, None)
                self._tree.addTopLevelItem(node)
            else:
                parent_node = get_or_create_dir(parts[:-1])
                node = QTreeWidgetItem(parent_node, [parts[-1]])
                node.setData(0, Qt.ItemDataRole.UserRole, None)
            node_map[key] = node
            return node

        for entry in entries:
            path_parts = Path(entry.internal_path).parts
            if len(path_parts) == 1:
                leaf = QTreeWidgetItem(self._tree, [path_parts[0]])
                leaf.setData(0, Qt.ItemDataRole.UserRole, entry)
                self._tree.addTopLevelItem(leaf)
            else:
                parent = get_or_create_dir(path_parts[:-1])
                leaf = QTreeWidgetItem(parent, [path_parts[-1]])
                leaf.setData(0, Qt.ItemDataRole.UserRole, entry)

        self._tree.expandAll()
        logger.debug("Refreshed tree with %d entries (pop_only=%s)", len(entries), self._show_pop_only)

    # ------------------------------------------------------------------ tree selection

    def _on_tree_item_selected(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        if current is None:
            return
        entry: ArchiveEntry | None = current.data(0, Qt.ItemDataRole.UserRole)
        if entry is None or not entry.is_population_file():
            return
        self._current_file_label.setText(f"{entry.archive_path.name} :: {entry.internal_path}")
        try:
            genomes = read_population_from_archive(entry)
        except Exception as exc:
            QMessageBox.warning(self, "Error reading population", str(exc))
            logger.warning("Failed to read population from %s: %s", entry.internal_path, exc)
            genomes = []
        self._populate_genome_table(genomes)

    def _populate_genome_table(self, genomes: list[GenomeEntry]) -> None:
        self._current_genomes = genomes
        self._genome_table.setRowCount(len(genomes))
        for i, g in enumerate(genomes):
            self._genome_table.setItem(i, 0, QTableWidgetItem(str(i)))
            self._genome_table.setItem(i, 1, QTableWidgetItem(str(g.instruction_count)))
            fitness_str = f"{g.fitness:.4f}" if g.fitness is not None else "—"
            self._genome_table.setItem(i, 2, QTableWidgetItem(fitness_str))
            # Preview: first 40 chars of dna_repr
            preview = g.dna_repr[:40] + ("…" if len(g.dna_repr) > 40 else "")
            self._genome_table.setItem(i, 3, QTableWidgetItem(preview))
        logger.debug("Populated genome table with %d genomes", len(genomes))

    # ------------------------------------------------------------------ middle buttons

    def _on_view_in_inspector(self) -> None:
        selected_rows = self._genome_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row >= len(self._current_genomes):
            return
        genome = self._current_genomes[row]
        self.view_genome_requested.emit(genome.dna)
        logger.debug("Emitted view_genome_requested for genome at row %d", row)

    def _on_add_to_selection(self) -> None:
        selected_rows = self._genome_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        added = 0
        for index in selected_rows:
            row = index.row()
            if row >= len(self._current_genomes):
                continue
            genome = self._current_genomes[row]
            if genome not in self._export_genomes:
                self._export_genomes.append(genome)
                item = QListWidgetItem(f"[{len(self._export_genomes) - 1}] {genome.dna_repr[:50]}")
                item.setData(Qt.ItemDataRole.UserRole, len(self._export_genomes) - 1)
                self._export_list.addItem(item)
                added += 1
        logger.debug("Added %d genomes to export selection (total: %d)", added, len(self._export_genomes))

    # ------------------------------------------------------------------ export pane

    def _on_remove_from_export(self) -> None:
        row = self._export_list.currentRow()
        if row < 0:
            return
        self._export_genomes.pop(row)
        self._export_list.takeItem(row)
        # Refresh labels
        for i in range(self._export_list.count()):
            item = self._export_list.item(i)
            if item:
                genome = self._export_genomes[i]
                item.setText(f"[{i}] {genome.dna_repr[:50]}")
                item.setData(Qt.ItemDataRole.UserRole, i)

    def _on_clear_export(self) -> None:
        self._export_genomes = []
        self._export_list.clear()
        logger.debug("Cleared export selection")

    def _on_save_population(self) -> None:
        if not self._export_genomes:
            QMessageBox.information(self, "Empty selection", "No genomes in export selection.")
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Population File", str(Path.home()),
            "Population files (*.pop);;Python files (*.py);;All files (*)"
        )
        if not path_str:
            return
        save_path = Path(path_str)
        try:
            lines = [g.dna_repr for g in self._export_genomes]
            save_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            QMessageBox.information(self, "Saved", f"Saved {len(lines)} genomes to {save_path.name}")
            logger.debug("Saved %d genomes to %s", len(lines), save_path)
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))

    def _on_import_to_library(self) -> None:
        if not self._export_genomes:
            QMessageBox.information(self, "Empty selection", "No genomes in export selection.")
            return
        dna_reprs = [g.dna_repr for g in self._export_genomes]
        self.import_to_library_requested.emit(dna_reprs)
        logger.debug("Emitted import_to_library_requested with %d genomes", len(dna_reprs))


class ArchiveManagerPanel(QWidget):
    """Archive Manager with two sub-tabs: Archive Browser and Population Library."""

    def __init__(
        self,
        app_state: AppState,
        library: PopulationLibrary,
        vm_inspector_panel: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._library = library
        self._vm_inspector_panel = vm_inspector_panel
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._sub_tabs = QTabWidget()

        self._archive_browser = ArchiveBrowserWidget()
        self._sub_tabs.addTab(self._archive_browser, "Archive Browser")

        self._pop_library_panel = PopulationLibraryPanel(self._app_state, self._library)
        self._sub_tabs.addTab(self._pop_library_panel, "Population Library")

        # Wire connections
        self._archive_browser.view_genome_requested.connect(self._on_view_genome)
        self._archive_browser.import_to_library_requested.connect(
            self._pop_library_panel.import_from_selection
        )
        self._pop_library_panel.open_in_inspector_requested.connect(self._on_view_genome)

        layout.addWidget(self._sub_tabs)

    def _on_view_genome(self, dna: list) -> None:
        if self._vm_inspector_panel is not None:
            self._vm_inspector_panel.load_dna(dna)
            logger.debug("Forwarded genome to VM inspector panel")
