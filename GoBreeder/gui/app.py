from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from GoBreeder.gui.main_window import MainWindow
from GoBreeder.gui.models.app_state import AppState

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GoBreeder")
    app.setOrganizationName("GoBreeder")

    state = AppState()
    window = MainWindow(app_state=state)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
