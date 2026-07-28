from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path.home() / ".alphacam"


def setup_logger(verbose: bool = False) -> logging.Logger:
    """Configure and return the alphacam logger with file rotation.

    Args:
        verbose: If True, set level to DEBUG; otherwise INFO.
    """
    log_dir = LOG_DIR
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_dir = Path.cwd() / ".alphacam"
        log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "alphacam.log"

    logger = logging.getLogger("alphacam")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if logger.handlers:
        return logger

    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10_485_760,
        backupCount=3,
        encoding="utf-8",
    )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = logging.getLogger("alphacam")
