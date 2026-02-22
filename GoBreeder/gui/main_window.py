from __future__ import annotations

import logging

from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget, QWidget

from GoBreeder.gui.models.app_state import AppState
from GoBreeder.gui.models.population_library import PopulationLibrary
from GoBreeder.gui.models.run_registry import RunRegistry
from GoBreeder.gui.panels.archive_manager_panel import ArchiveManagerPanel
from GoBreeder.gui.panels.breeding_runs_panel import BreedingRunsPanel
from GoBreeder.gui.panels.deployment_panel import DeploymentPanel
from GoBreeder.gui.panels.vm_inspector_panel import VMInspectorPanel

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, app_state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self.setWindowTitle("GoBreeder")
        self.resize(1200, 800)
        self._build_ui()
        app_state.deployments_changed.connect(self._update_status_bar)
        self._update_status_bar()

    def _build_ui(self) -> None:
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # Population Library (shared across panels)
        self._population_library = PopulationLibrary(parent=self)

        # Tab 0: Deployments
        self._deployment_panel = DeploymentPanel(self._app_state, self._population_library)
        self._tabs.addTab(self._deployment_panel, "Deployments")

        # Tab 1: Breeding Runs
        self._run_registry = RunRegistry(parent=self)
        self._breeding_runs_panel = BreedingRunsPanel(self._app_state, self._run_registry)
        self._tabs.addTab(self._breeding_runs_panel, "Breeding Runs")

        # Wire deployment panel -> runs panel
        self._deployment_panel.go_to_run_requested.connect(self._on_go_to_run)

        # Tab 2: VM Inspector
        self._vm_inspector_panel = VMInspectorPanel(self._app_state)
        self._tabs.addTab(self._vm_inspector_panel, "VM Inspector")

        # Tab 3: Archive Manager
        self._archive_manager_panel = ArchiveManagerPanel(
            self._app_state,
            self._population_library,
            vm_inspector_panel=self._vm_inspector_panel,
        )
        self._tabs.addTab(self._archive_manager_panel, "Archive Manager")

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    def _on_go_to_run(self, deployment_name: str) -> None:
        self.switch_to_tab("Breeding Runs")
        self._breeding_runs_panel.select_deployment(deployment_name)

    def _update_status_bar(self) -> None:
        running = sum(1 for d in self._app_state.deployments if d.is_running())
        total = len(self._app_state.deployments)
        self._status_bar.showMessage(f"Deployments: {total}  |  Active runs: {running}")

    def switch_to_tab(self, tab_name: str) -> None:
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == tab_name:
                self._tabs.setCurrentIndex(i)
                break
