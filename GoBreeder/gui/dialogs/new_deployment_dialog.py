from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class NewDeploymentDialog(QDialog):
    """Dialog for creating a new deployment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Deployment")
        self.setMinimumWidth(500)
        self._result_name: str = ""
        self._result_dir: Path = Path.home()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. breeder_01")

        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Parent directory")
        self._dir_edit.setText(str(Path.home()))
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_dir)

        dir_row = QWidget()
        dir_layout = QHBoxLayout(dir_row)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.addWidget(self._dir_edit)
        dir_layout.addWidget(browse_btn)

        form.addRow("Deployment Name:", self._name_edit)
        form.addRow("Parent Directory:", dir_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Parent Directory", self._dir_edit.text()
        )
        if path:
            self._dir_edit.setText(path)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        parent_dir = Path(self._dir_edit.text().strip())

        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a deployment name.")
            return
        invalid_chars = set('/\\:*?"<>|')
        if any(c in invalid_chars for c in name):
            QMessageBox.warning(self, "Validation", "Name contains invalid characters.")
            return
        if not parent_dir.exists():
            QMessageBox.warning(self, "Validation", "Parent directory does not exist.")
            return
        if not parent_dir.is_dir():
            QMessageBox.warning(self, "Validation", "Parent path is not a directory.")
            return

        self._result_name = name
        self._result_dir = parent_dir
        self.accept()

    def get_result(self) -> tuple[str, Path]:
        """Return (name, parent_dir) after dialog accepted."""
        return self._result_name, self._result_dir
