"""Implements background file I/O operations using threads."""


import logging
import threading

logger = logging.getLogger(__name__)


def log(msg: str) -> None:
    """Forward to Python logger at DEBUG level."""
    logger.debug("threaded_fileops: %s", msg)


def threaded_writelines(data, filehandle):
    threading.Thread(target=_threaded_writelines, args=(data, filehandle)).start()
    log("write thread created")


def _threaded_writelines(data, filehandle):
    if data[0]:
        if not data[0][-1] == "\n":  # if the first element doesnt have '\n' assume they all dont
            data = [d + "\n" for d in data]
            # must be a better way
    with filehandle as filehandle:
        filehandle.writelines(data)
        log("write thread fin")
