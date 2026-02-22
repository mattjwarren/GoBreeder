from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from GoBreeder.gui.models.breeding_run_controller import BreedingRunController
from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.run_state import RunState

logger = logging.getLogger(__name__)


class RunRegistry(QObject):
    """
    Tracks active BreedingRunController instances mapped to deployments.
    Owned by AppState or MainWindow. Manages run lifecycle.
    """

    run_state_changed = Signal(str, str)  # (deployment_name, new_state)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._controllers: dict[str, BreedingRunController] = {}

    def start(self, deployment: DeploymentModel, app_state: object) -> None:
        """Start a breeding run for the deployment."""
        if deployment.name in self._controllers:
            logger.warning("Run already active for %r — ignoring start request", deployment.name)
            return
        controller = BreedingRunController(parent=self)
        self._controllers[deployment.name] = controller
        controller.run_finished.connect(lambda dep=deployment, app=app_state: self._on_finished(dep, app))
        controller.run_failed.connect(lambda msg, dep=deployment, app=app_state: self._on_failed(dep, msg, app))
        deployment.run_state = RunState.RUNNING
        app_state.update_deployment(deployment)  # type: ignore[union-attr]
        controller.start(deployment)
        self.run_state_changed.emit(deployment.name, RunState.RUNNING.value)
        logger.info("Started breeding run for %r", deployment.name)

    def stop(self, deployment: DeploymentModel, app_state: object) -> None:
        """Stop a breeding run for the deployment."""
        controller = self._controllers.get(deployment.name)
        if controller is None:
            logger.warning("No active run for %r to stop", deployment.name)
            return
        deployment.run_state = RunState.STOPPING
        app_state.update_deployment(deployment)  # type: ignore[union-attr]
        self.run_state_changed.emit(deployment.name, RunState.STOPPING.value)
        controller.stop()

    def _on_finished(self, deployment: DeploymentModel, app_state: object) -> None:
        self._controllers.pop(deployment.name, None)
        deployment.run_state = RunState.IDLE
        app_state.update_deployment(deployment)  # type: ignore[union-attr]
        self.run_state_changed.emit(deployment.name, RunState.IDLE.value)
        logger.info("Breeding run finished for %r", deployment.name)

    def _on_failed(self, deployment: DeploymentModel, message: str, app_state: object) -> None:
        self._controllers.pop(deployment.name, None)
        deployment.run_state = RunState.IDLE
        app_state.update_deployment(deployment)  # type: ignore[union-attr]
        self.run_state_changed.emit(deployment.name, RunState.IDLE.value)
        logger.error("Breeding run failed for %r: %s", deployment.name, message)

    def is_running(self, deployment: DeploymentModel) -> bool:
        return deployment.name in self._controllers

    def controller_for(self, deployment_name: str) -> BreedingRunController | None:
        return self._controllers.get(deployment_name)
