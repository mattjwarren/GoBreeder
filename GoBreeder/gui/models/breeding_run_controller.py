from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QProcess, Signal

from GoBreeder.gui.models.deployment import DeploymentModel

logger = logging.getLogger(__name__)


class BreedingRunController(QObject):
    """Manages a single breeding run subprocess using QProcess."""

    log_line_received = Signal(str)
    generation_advanced = Signal(int)
    run_finished = Signal()
    run_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._generation: int = 0
        self._deployment: DeploymentModel | None = None

    @property
    def generation(self) -> int:
        return self._generation

    def start(self, deployment: DeploymentModel) -> None:
        """Start the breeding run subprocess."""
        self._deployment = deployment
        self._generation = 0

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(deployment.breed_dir))
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        genome_file = str(deployment.population_file_path())
        mediator = str(deployment.breed_dir / "mediator.py")

        program = "uv"
        if sys.platform == "win32":
            args = ["run", "python", mediator, "-gtp_breed", "-genome_file", genome_file]
        else:
            args = ["run", "python3", mediator, "-gtp_breed", "-genome_file", genome_file]

        logger.debug("Starting process: %s %s", program, " ".join(args))
        self._process.start(program, args)
        if not self._process.waitForStarted(3000):
            error = self._process.errorString()
            logger.error("Failed to start process: %s", error)
            self.run_failed.emit(f"Failed to start: {error}")

    def stop(self) -> None:
        """Stop the breeding run, gracefully then forcibly."""
        if self._process is None:
            return
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(5000):
                logger.warning("Process did not terminate gracefully; killing")
                self._process.kill()
                self._process.waitForFinished(2000)

    def _parse_line(self, line: str) -> None:
        """Parse a log line and emit signals."""
        self.log_line_received.emit(line.rstrip("\r\n"))
        lower = line.lower()
        if "breeding generation" in lower:
            parts = lower.split("breeding generation")
            if len(parts) > 1:
                try:
                    gen_str = parts[1].strip().split()[0]
                    gen = int(gen_str)
                    self._generation = gen
                    self.generation_advanced.emit(gen)
                    logger.debug("Generation advanced to %d", gen)
                except (IndexError, ValueError):
                    pass

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        for line in text.splitlines():
            self._parse_line(line)

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardError()
        text = bytes(data).decode("utf-8", errors="replace")
        for line in text.splitlines():
            self._parse_line(line)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        logger.info("Process finished with exit code %d, status %s", exit_code, exit_status)
        if exit_status == QProcess.ExitStatus.NormalExit:
            self.run_finished.emit()
        else:
            self.run_failed.emit(f"Process crashed (exit code {exit_code})")
        self._process = None

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if self._process:
            msg = self._process.errorString()
        else:
            msg = str(error)
        logger.error("QProcess error: %s", msg)
        self.run_failed.emit(msg)
        self._process = None
