from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from GoBreeder.gui.models.deployment import DeploymentModel

logger = logging.getLogger(__name__)


class AppState(QObject):
    deployments_changed = Signal()

    def __init__(self, registry_path: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._deployments: list[DeploymentModel] = []
        if registry_path is None:
            registry_path = Path.home() / ".gobreeder" / "deployments.json"
        self._registry_path = registry_path
        self._load()

    @property
    def deployments(self) -> list[DeploymentModel]:
        return list(self._deployments)

    def add_deployment(self, deployment: DeploymentModel) -> None:
        logger.debug("Adding deployment: %s", deployment.name)
        self._deployments.append(deployment)
        self._save()
        self.deployments_changed.emit()

    def remove_deployment(self, deployment: DeploymentModel) -> None:
        logger.debug("Removing deployment: %s", deployment.name)
        self._deployments = [d for d in self._deployments if d.name != deployment.name]
        self._save()
        self.deployments_changed.emit()

    def update_deployment(self, deployment: DeploymentModel) -> None:
        logger.debug("Updating deployment: %s", deployment.name)
        for i, d in enumerate(self._deployments):
            if d.name == deployment.name:
                self._deployments[i] = deployment
                break
        self._save()
        self.deployments_changed.emit()

    def _save(self) -> None:
        logger.debug("Saving deployment registry to: %s", self._registry_path)
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = [d.model_dump(mode="json") for d in self._deployments]
        self._registry_path.write_text(json.dumps(data, indent=2, default=str))
        logger.debug("Saved %d deployments", len(data))

    def _load(self) -> None:
        logger.debug("Loading deployment registry from: %s", self._registry_path)
        if not self._registry_path.exists():
            logger.debug("Registry file does not exist, starting empty")
            return
        try:
            raw = json.loads(self._registry_path.read_text())
            self._deployments = [DeploymentModel.model_validate(item) for item in raw]
            logger.debug("Loaded %d deployments", len(self._deployments))
        except Exception as exc:
            logger.warning("Failed to load deployment registry: %s", exc)
            self._deployments = []
