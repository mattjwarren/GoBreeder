from __future__ import annotations

from pathlib import Path

import pytest

from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.deployment_manager import DeploymentManager, DeploymentManagerError
from GoBreeder.gui.models.run_state import RunState


def _make_model(deployment_dir: Path, run_state: RunState = RunState.IDLE) -> DeploymentModel:
    return DeploymentModel(
        name="test_deployment",
        deployment_dir=deployment_dir,
        run_state=run_state,
    )


class TestDeploymentManager:
    def test_delete_removes_directory(self, tmp_path: Path) -> None:
        deploy_dir = tmp_path / "my_deployment"
        deploy_dir.mkdir()
        (deploy_dir / "breed").mkdir()

        model = _make_model(deploy_dir)
        manager = DeploymentManager()
        manager.delete(model)

        assert not deploy_dir.exists()

    def test_delete_running_raises_error(self, tmp_path: Path) -> None:
        deploy_dir = tmp_path / "my_deployment"
        deploy_dir.mkdir()

        model = _make_model(deploy_dir, run_state=RunState.RUNNING)
        manager = DeploymentManager()

        with pytest.raises(DeploymentManagerError, match="Cannot delete running deployment"):
            manager.delete(model)

        # Directory should still exist
        assert deploy_dir.exists()

    def test_delete_nonexistent_directory_does_not_raise(self, tmp_path: Path) -> None:
        deploy_dir = tmp_path / "nonexistent"
        model = _make_model(deploy_dir)
        manager = DeploymentManager()

        # Should not raise - just logs a warning
        manager.delete(model)

    def test_delete_nested_contents(self, tmp_path: Path) -> None:
        """Verify that rmtree removes all nested contents."""
        deploy_dir = tmp_path / "my_deployment"
        breed_dir = deploy_dir / "breed"
        breed_dir.mkdir(parents=True)
        (breed_dir / "config.py").write_text("basepath = '/tmp'\n")
        (breed_dir / "current_population.py").write_text("# empty\n")

        model = _make_model(deploy_dir)
        manager = DeploymentManager()
        manager.delete(model)

        assert not deploy_dir.exists()

    def test_stopping_state_is_not_running(self, tmp_path: Path) -> None:
        """A deployment in STOPPING state should be deletable (not considered running)."""
        deploy_dir = tmp_path / "my_deployment"
        deploy_dir.mkdir()

        model = _make_model(deploy_dir, run_state=RunState.STOPPING)
        manager = DeploymentManager()

        # STOPPING is not is_running(), so delete should succeed
        manager.delete(model)
        assert not deploy_dir.exists()
