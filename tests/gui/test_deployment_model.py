from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.run_state import RunState


class TestDeploymentModelPaths:
    def test_breed_dir_computed_from_deployment_dir(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.breed_dir == tmp_path / "breed"

    def test_population_file_path(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.population_file_path() == tmp_path / "breed" / "current_population.py"

    def test_previous_population_file_path(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.previous_population_file_path() == tmp_path / "breed" / "current_population.py_save"

    def test_stats_file_path(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.stats_file_path() == tmp_path / "breed" / "current_population.py_save_stats"

    def test_runlog_path(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.runlog_path() == tmp_path / "breed" / "runlog.txt"


class TestDeploymentModelRunState:
    def test_is_running_false_when_idle(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.is_running() is False

    def test_is_running_true_when_running(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path, run_state=RunState.RUNNING)
        assert dep.is_running() is True

    def test_is_running_false_when_stopping(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path, run_state=RunState.STOPPING)
        assert dep.is_running() is False

    def test_default_run_state_is_idle(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.run_state == RunState.IDLE


class TestDeploymentModelDefaults:
    def test_created_at_defaults_to_recent_datetime(self, tmp_path: Path) -> None:
        before = datetime.now()
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        after = datetime.now()
        assert before <= dep.created_at <= after

    def test_name_field(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="my-deployment", deployment_dir=tmp_path)
        assert dep.name == "my-deployment"

    def test_deployment_dir_field(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.deployment_dir == tmp_path


class TestDeploymentModelSerialization:
    def test_json_round_trip(self, tmp_path: Path) -> None:
        dep = DeploymentModel(
            name="round-trip",
            deployment_dir=tmp_path,
            run_state=RunState.RUNNING,
        )
        data = dep.model_dump(mode="json")

        # Path fields should be strings in JSON mode
        assert isinstance(data["deployment_dir"], str)
        assert isinstance(data["breed_dir"], str)

        # Round-trip through model_validate
        restored = DeploymentModel.model_validate(data)
        assert restored.name == dep.name
        assert restored.deployment_dir == dep.deployment_dir
        assert restored.breed_dir == dep.breed_dir
        assert restored.run_state == dep.run_state

    def test_breed_dir_not_in_input_data(self, tmp_path: Path) -> None:
        """breed_dir is computed; constructing without it should still work."""
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        assert dep.breed_dir == tmp_path / "breed"

    def test_json_dump_contains_expected_keys(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        data = dep.model_dump(mode="json")
        assert "name" in data
        assert "deployment_dir" in data
        assert "breed_dir" in data
        assert "created_at" in data
        assert "run_state" in data

    def test_run_state_serialized_as_string_value(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path, run_state=RunState.RUNNING)
        data = dep.model_dump(mode="json")
        assert data["run_state"] == "RUNNING"

    def test_python_mode_dump_keeps_path_objects(self, tmp_path: Path) -> None:
        dep = DeploymentModel(name="test", deployment_dir=tmp_path)
        data = dep.model_dump()
        assert isinstance(data["deployment_dir"], Path)

    def test_restore_from_json_with_string_paths(self, tmp_path: Path) -> None:
        raw = {
            "name": "from-str",
            "deployment_dir": str(tmp_path),
            "run_state": "IDLE",
            "created_at": datetime.now().isoformat(),
        }
        dep = DeploymentModel.model_validate(raw)
        assert dep.deployment_dir == tmp_path
        assert dep.breed_dir == tmp_path / "breed"
