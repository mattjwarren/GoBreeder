"""Centralized logging configuration for GoBreeder.

Configures the Python logging hierarchy so that:
- DEBUG and above goes to STDOUT.
- DEBUG and above goes to a rotating file in logs/ next to the breed/ directory.

Call ``setup_logging(log_dir)`` once at application startup (e.g. from mediator.py
or breeder.py).  All other modules should just use::

    import logging
    logger = logging.getLogger(__name__)
    logger.debug("...")
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str, level: int = logging.DEBUG) -> None:
    """Configure root logger with a StreamHandler (stdout) + RotatingFileHandler.

    Parameters
    ----------
    log_dir:
        Directory in which to create ``gobreeder.log``.  Created if absent.
    level:
        Root logging level (default DEBUG).
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "gobreeder.log")

    root = logging.getLogger()
    if root.handlers:
        # Already configured – skip to avoid duplicate handlers if re-imported.
        return

    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(name)-20s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # STDOUT handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    # Rotating file handler (10 MB max, keep 5 backups)
    file_handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # The VM module is extremely verbose at DEBUG level. Suppress to WARNING
    # by default so breeding run logs stay readable.  Set to DEBUG explicitly
    # if you need low-level VM opcode tracing.
    logging.getLogger("vm").setLevel(logging.WARNING)
