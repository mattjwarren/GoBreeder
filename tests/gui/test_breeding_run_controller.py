from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytestqt.qtbot import QtBot

from GoBreeder.gui.models.breeding_run_controller import BreedingRunController
from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.run_state import RunState


@pytest.fixture()
def deployment(tmp_path: Path) -> DeploymentModel:
    breed_dir = tmp_path / "breed"
    breed_dir.mkdir()
    return DeploymentModel(name="test-dep", deployment_dir=tmp_path, run_state=RunState.IDLE)


class TestBreedingRunControllerInit:
    def test_initial_generation_is_zero(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()
        assert ctrl.generation == 0

    def test_no_process_on_init(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()
        assert ctrl._process is None


class TestBreedingRunControllerParseLine:
    def test_log_line_received_emitted_for_every_line(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()
        received: list[str] = []
        ctrl.log_line_received.connect(received.append)

        ctrl._parse_line("hello world")
        ctrl._parse_line("another line")

        assert received == ["hello world", "another line"]

    def test_generation_advanced_emitted_on_breeding_generation_line(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()

        with qtbot.waitSignal(ctrl.generation_advanced, timeout=1000) as blocker:
            ctrl._parse_line("breeding generation 5")

        assert blocker.args == [5]

    def test_generation_counter_increments(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()

        ctrl._parse_line("breeding generation 3")
        assert ctrl.generation == 3

        ctrl._parse_line("breeding generation 7")
        assert ctrl.generation == 7

    def test_generation_advanced_not_emitted_for_non_generation_line(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()
        generations: list[int] = []
        ctrl.generation_advanced.connect(generations.append)

        ctrl._parse_line("some random output line")

        assert generations == []

    def test_parse_line_strips_trailing_newlines(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()
        received: list[str] = []
        ctrl.log_line_received.connect(received.append)

        ctrl._parse_line("hello\r\n")

        assert received == ["hello"]

    def test_malformed_generation_line_no_crash(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()
        generations: list[int] = []
        ctrl.generation_advanced.connect(generations.append)

        # "breeding generation" with no number following
        ctrl._parse_line("breeding generation")
        ctrl._parse_line("breeding generation abc")

        assert generations == []

    def test_generation_line_case_insensitive(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()

        with qtbot.waitSignal(ctrl.generation_advanced, timeout=1000) as blocker:
            ctrl._parse_line("BREEDING GENERATION 10")

        assert blocker.args == [10]


class TestBreedingRunControllerStart:
    def test_start_configures_qprocess(self, qtbot: QtBot, deployment: DeploymentModel) -> None:
        ctrl = BreedingRunController()

        mock_process = MagicMock()
        mock_process.waitForStarted.return_value = True
        mock_process.state.return_value = MagicMock()

        from PySide6.QtCore import QProcess

        with patch.object(QProcess, "__init__", return_value=None), \
             patch("GoBreeder.gui.models.breeding_run_controller.QProcess") as MockQProcess:
            mock_process_instance = MagicMock()
            mock_process_instance.waitForStarted.return_value = True
            MockQProcess.return_value = mock_process_instance

            ctrl.start(deployment)

            mock_process_instance.setWorkingDirectory.assert_called_once_with(
                str(deployment.breed_dir)
            )
            assert mock_process_instance.start.called

    def test_start_resets_generation(self, qtbot: QtBot, deployment: DeploymentModel) -> None:
        ctrl = BreedingRunController()
        ctrl._generation = 42

        from GoBreeder.gui.models import breeding_run_controller as brc_module
        with patch("GoBreeder.gui.models.breeding_run_controller.QProcess") as MockQProcess:
            mock_process_instance = MagicMock()
            mock_process_instance.waitForStarted.return_value = True
            MockQProcess.return_value = mock_process_instance

            ctrl.start(deployment)

        assert ctrl.generation == 0


class TestBreedingRunControllerStop:
    def test_stop_when_no_process_does_nothing(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()
        # Should not raise
        ctrl.stop()

    def test_stop_calls_terminate(self, qtbot: QtBot, deployment: DeploymentModel) -> None:
        ctrl = BreedingRunController()

        from PySide6.QtCore import QProcess

        mock_process = MagicMock()
        mock_process.state.return_value = QProcess.ProcessState.Running
        mock_process.waitForFinished.return_value = True
        ctrl._process = mock_process  # type: ignore[assignment]

        ctrl.stop()

        mock_process.terminate.assert_called_once()

    def test_stop_kills_if_terminate_fails(self, qtbot: QtBot) -> None:
        ctrl = BreedingRunController()

        from PySide6.QtCore import QProcess

        mock_process = MagicMock()
        mock_process.state.return_value = QProcess.ProcessState.Running
        mock_process.waitForFinished.return_value = False  # terminate did not work
        ctrl._process = mock_process  # type: ignore[assignment]

        ctrl.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
