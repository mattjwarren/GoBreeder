from __future__ import annotations

import json
from pathlib import Path

import pytest

from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.run_state import RunState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

try:
    from PySide6.QtCore import QCoreApplication
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

requires_pyside6 = pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 not installed")


def _make_deployment(tmp_path: Path, name: str = "dep1", run_state: RunState = RunState.IDLE) -> DeploymentModel:
    return DeploymentModel(name=name, deployment_dir=tmp_path / name, run_state=run_state)


# ---------------------------------------------------------------------------
# AppState import (guarded so pure-pydantic tests still pass without Qt)
# ---------------------------------------------------------------------------

if PYSIDE6_AVAILABLE:
    from GoBreeder.gui.models.app_state import AppState


# ---------------------------------------------------------------------------
# Tests that require PySide6
# ---------------------------------------------------------------------------

@requires_pyside6
class TestAppStateAddRemove:
    def test_add_deployment(self, tmp_path: Path) -> None:
        state = AppState(registry_path=tmp_path / "reg.json")
        dep = _make_deployment(tmp_path)
        state.add_deployment(dep)
        assert len(state.deployments) == 1
        assert state.deployments[0].name == "dep1"

    def test_remove_deployment(self, tmp_path: Path) -> None:
        state = AppState(registry_path=tmp_path / "reg.json")
        dep = _make_deployment(tmp_path)
        state.add_deployment(dep)
        state.remove_deployment(dep)
        assert len(state.deployments) == 0

    def test_add_multiple_deployments(self, tmp_path: Path) -> None:
        state = AppState(registry_path=tmp_path / "reg.json")
        for i in range(3):
            state.add_deployment(_make_deployment(tmp_path, name=f"dep{i}"))
        assert len(state.deployments) == 3

    def test_remove_nonexistent_deployment_is_noop(self, tmp_path: Path) -> None:
        state = AppState(registry_path=tmp_path / "reg.json")
        dep = _make_deployment(tmp_path)
        # Should not raise
        state.remove_deployment(dep)
        assert len(state.deployments) == 0

    def test_update_deployment(self, tmp_path: Path) -> None:
        state = AppState(registry_path=tmp_path / "reg.json")
        dep = _make_deployment(tmp_path)
        state.add_deployment(dep)

        updated = DeploymentModel(
            name=dep.name,
            deployment_dir=dep.deployment_dir,
            run_state=RunState.RUNNING,
        )
        state.update_deployment(updated)
        assert state.deployments[0].run_state == RunState.RUNNING


@requires_pyside6
class TestAppStatePersistence:
    def test_persist_and_restore(self, tmp_path: Path) -> None:
        registry = tmp_path / "reg.json"
        state1 = AppState(registry_path=registry)
        dep = _make_deployment(tmp_path, name="persist-me")
        state1.add_deployment(dep)

        # New instance from same path
        state2 = AppState(registry_path=registry)
        assert len(state2.deployments) == 1
        assert state2.deployments[0].name == "persist-me"

    def test_persist_multiple_and_restore(self, tmp_path: Path) -> None:
        registry = tmp_path / "reg.json"
        state1 = AppState(registry_path=registry)
        for i in range(3):
            state1.add_deployment(_make_deployment(tmp_path, name=f"dep{i}"))

        state2 = AppState(registry_path=registry)
        assert len(state2.deployments) == 3
        names = {d.name for d in state2.deployments}
        assert names == {"dep0", "dep1", "dep2"}

    def test_registry_file_is_valid_json(self, tmp_path: Path) -> None:
        registry = tmp_path / "reg.json"
        state = AppState(registry_path=registry)
        state.add_deployment(_make_deployment(tmp_path))
        data = json.loads(registry.read_text())
        assert isinstance(data, list)
        assert len(data) == 1

    def test_remove_persists(self, tmp_path: Path) -> None:
        registry = tmp_path / "reg.json"
        state1 = AppState(registry_path=registry)
        dep = _make_deployment(tmp_path)
        state1.add_deployment(dep)
        state1.remove_deployment(dep)

        state2 = AppState(registry_path=registry)
        assert len(state2.deployments) == 0


@requires_pyside6
class TestAppStateRobustness:
    def test_missing_registry_file_starts_empty(self, tmp_path: Path) -> None:
        registry = tmp_path / "nonexistent" / "reg.json"
        state = AppState(registry_path=registry)
        assert state.deployments == []

    def test_corrupt_registry_handled_gracefully(self, tmp_path: Path) -> None:
        registry = tmp_path / "reg.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text("THIS IS NOT VALID JSON }{")
        # Should not raise
        state = AppState(registry_path=registry)
        assert state.deployments == []

    def test_empty_json_array_registry(self, tmp_path: Path) -> None:
        registry = tmp_path / "reg.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text("[]")
        state = AppState(registry_path=registry)
        assert state.deployments == []


@requires_pyside6
class TestAppStateSignals:
    def test_deployments_changed_emitted_on_add(self, tmp_path: Path, qtbot) -> None:
        state = AppState(registry_path=tmp_path / "reg.json")
        dep = _make_deployment(tmp_path)
        with qtbot.waitSignal(state.deployments_changed, timeout=1000):
            state.add_deployment(dep)

    def test_deployments_changed_emitted_on_remove(self, tmp_path: Path, qtbot) -> None:
        state = AppState(registry_path=tmp_path / "reg.json")
        dep = _make_deployment(tmp_path)
        state.add_deployment(dep)
        with qtbot.waitSignal(state.deployments_changed, timeout=1000):
            state.remove_deployment(dep)

    def test_deployments_changed_emitted_on_update(self, tmp_path: Path, qtbot) -> None:
        state = AppState(registry_path=tmp_path / "reg.json")
        dep = _make_deployment(tmp_path)
        state.add_deployment(dep)
        updated = DeploymentModel(
            name=dep.name,
            deployment_dir=dep.deployment_dir,
            run_state=RunState.RUNNING,
        )
        with qtbot.waitSignal(state.deployments_changed, timeout=1000):
            state.update_deployment(updated)

    def test_deployments_changed_callback_called(self, tmp_path: Path) -> None:
        """Test signal via callback, no qtbot required."""
        state = AppState(registry_path=tmp_path / "reg.json")
        calls: list[int] = []
        state.deployments_changed.connect(lambda: calls.append(1))
        dep = _make_deployment(tmp_path)
        state.add_deployment(dep)
        assert len(calls) == 1
        state.remove_deployment(dep)
        assert len(calls) == 2
