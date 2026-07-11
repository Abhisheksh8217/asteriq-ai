"""
logger.py
---------
Centralized logging configuration for the entire application.
All modules must use get_logger(__name__) instead of print().

Logs are written to both console and a rotating file in storage/logs/.
Log level is controlled via LOG_LEVEL in .env (default: INFO).
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from config import LOGS_DIR, LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT

# Ensure logs directory exists before setting up file handler
os.makedirs(LOGS_DIR, exist_ok=True)

# Track initialized loggers to avoid duplicate handlers
_initialized_loggers: set = set()


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger for the given module name.

    Usage:
        from logger import get_logger
        logger = get_logger(__name__)
        logger.info("Service started")
        logger.error("Something failed", exc_info=True)

    Args:
        name: Module name, typically __name__.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already configured
    if name in _initialized_loggers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler — always active
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler — max 5MB per file, keep 3 backups
    log_file = os.path.join(LOGS_DIR, "app.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent log messages from propagating to the root logger
    logger.propagate = False

    _initialized_loggers.add(name)
    return logger
