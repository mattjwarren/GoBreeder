from __future__ import annotations

import logging
import shutil

from GoBreeder.gui.models.deployment import DeploymentModel

logger = logging.getLogger(__name__)


class DeploymentManagerError(Exception):
    """Raised when a deployment management operation fails."""


class DeploymentManager:
    """Handles deployment lifecycle operations (deletion, etc.)."""

    def delete(self, deployment: DeploymentModel) -> None:
        """
        Delete a deployment directory.

        Raises DeploymentManagerError if the deployment is currently running.
        """
        if deployment.is_running():
            raise DeploymentManagerError(
                f"Cannot delete running deployment '{deployment.name}'. Stop it first."
            )
        if deployment.deployment_dir.exists():
            shutil.rmtree(deployment.deployment_dir)
            logger.info("Deleted deployment directory: %s", deployment.deployment_dir)
        else:
            logger.warning(
                "Deployment directory not found (already deleted?): %s",
                deployment.deployment_dir,
            )
