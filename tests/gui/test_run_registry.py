from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytestqt.qtbot import QtBot

from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.run_registry import RunRegistry
from GoBreeder.gui.models.run_state import RunState


class MockAppState:
    def __init__(self) -> None:
        self.updated: list[DeploymentModel] = []

    def update_deployment(self, d: DeploymentModel) -> None:
        self.updated.append(d)


@pytest.fixture()
def deployment(tmp_path: Path) -> DeploymentModel:
    breed_dir = tmp_path / "breed"
    breed_dir.mkdir()
    return DeploymentModel(name="dep1", deployment_dir=tmp_path, run_state=RunState.IDLE)


@pytest.fixture()
def app_state() -> MockAppState:
    return MockAppState()


class TestRunRegistryInit:
    def test_no_controllers_on_init(self, qtbot: QtBot) -> None:
        registry = RunRegistry()
        assert registry._controllers == {}

    def test_is_running_false_on_init(self, qtbot: QtBot, deployment: DeploymentModel) -> None:
        registry = RunRegistry()
        assert registry.is_running(deployment) is False

    def test_controller_for_returns_none_on_init(self, qtbot: QtBot) -> None:
        registry = RunRegistry()
        assert registry.controller_for("nonexistent") is None


class TestRunRegistryStart:
    def test_start_sets_deployment_to_running(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl

            registry.start(deployment, app_state)

        assert deployment.run_state == RunState.RUNNING
        assert len(app_state.updated) >= 1
        assert app_state.updated[-1].name == "dep1"

    def test_start_registers_controller(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl

            registry.start(deployment, app_state)

        assert registry.is_running(deployment) is True
        assert registry.controller_for("dep1") is mock_ctrl

    def test_start_emits_run_state_changed(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl

            with qtbot.waitSignal(registry.run_state_changed, timeout=1000) as blocker:
                registry.start(deployment, app_state)

        assert blocker.args == ["dep1", RunState.RUNNING.value]

    def test_start_ignores_duplicate_start(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl

            registry.start(deployment, app_state)
            registry.start(deployment, app_state)  # duplicate; should be ignored

        # Only one controller created
        assert MockCtrl.call_count == 1


class TestRunRegistryStop:
    def test_stop_sets_deployment_to_stopping(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl

            registry.start(deployment, app_state)
            registry.stop(deployment, app_state)

        assert deployment.run_state == RunState.STOPPING

    def test_stop_calls_controller_stop(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl

            registry.start(deployment, app_state)
            registry.stop(deployment, app_state)

        mock_ctrl.stop.assert_called_once()

    def test_stop_emits_stopping_state(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()
        emitted: list[tuple[str, str]] = []
        registry.run_state_changed.connect(lambda n, s: emitted.append((n, s)))

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl

            registry.start(deployment, app_state)
            registry.stop(deployment, app_state)

        assert ("dep1", RunState.STOPPING.value) in emitted

    def test_stop_on_non_running_deployment_does_nothing(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()
        # Should not raise
        registry.stop(deployment, app_state)


class TestRunRegistryFinished:
    def test_on_finished_sets_idle_and_removes_controller(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl

            registry.start(deployment, app_state)

        registry._on_finished(deployment, app_state)

        assert deployment.run_state == RunState.IDLE
        assert not registry.is_running(deployment)

    def test_on_finished_emits_idle_state(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()
        emitted: list[tuple[str, str]] = []
        registry.run_state_changed.connect(lambda n, s: emitted.append((n, s)))

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl
            registry.start(deployment, app_state)

        registry._on_finished(deployment, app_state)

        assert ("dep1", RunState.IDLE.value) in emitted


class TestRunRegistryFailed:
    def test_on_failed_sets_idle_and_removes_controller(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl
            registry.start(deployment, app_state)

        registry._on_failed(deployment, "something went wrong", app_state)

        assert deployment.run_state == RunState.IDLE
        assert not registry.is_running(deployment)

    def test_on_failed_emits_idle_state(
        self, qtbot: QtBot, deployment: DeploymentModel, app_state: MockAppState
    ) -> None:
        registry = RunRegistry()
        emitted: list[tuple[str, str]] = []
        registry.run_state_changed.connect(lambda n, s: emitted.append((n, s)))

        with patch("GoBreeder.gui.models.run_registry.BreedingRunController") as MockCtrl:
            mock_ctrl = MagicMock()
            MockCtrl.return_value = mock_ctrl
            registry.start(deployment, app_state)

        registry._on_failed(deployment, "crash", app_state)

        assert ("dep1", RunState.IDLE.value) in emitted
