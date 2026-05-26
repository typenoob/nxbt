import logging
from datetime import datetime

from loguru import logger

_FORMAT = "[{time:YYYY-MM-DD HH:mm:ss.SSS}] {level} in {module}: {message}"


class _InterceptHandler(logging.Handler):
    """Forwards standard library logging records to loguru."""

    def emit(self, record):
        level = logger.level(record.levelname).name if record.levelname else "DEBUG"
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def _install_intercept_handlers():
    """Attach _InterceptHandler to nxbt/bumble loggers if not already present."""
    for name in ("nxbt", "bumble"):
        std_logger = logging.getLogger(name)
        if not any(isinstance(h, _InterceptHandler) for h in std_logger.handlers):
            std_logger.addHandler(_InterceptHandler())


def _configure_logger(debug=False, log_to_file=False, disable_logging=False):
    """Full loguru configuration — called at module import (defaults) and by create_logger (override)."""
    level = "DEBUG" if debug else "INFO"

    # Clear existing loguru sinks and rebuild
    logger.remove()

    if disable_logging:
        return

    if log_to_file:
        log_filename = (
            log_to_file
            if isinstance(log_to_file, str)
            else f"./nxbt {datetime.now()}.log"
        )
        logger.add(log_filename, format=_FORMAT, level=level, enqueue=True)
    else:
        logger.add(
            lambda msg: print(msg, end=""), format=_FORMAT, level=level, enqueue=True
        )

    # Set levels on nxbt/bumble stdlib loggers
    for name in ("nxbt", "bumble"):
        std_logger = logging.getLogger(name)
        std_logger.setLevel(level)


# Auto-configure on import so child/grandchild processes get logging immediately.
# Default to DEBUG level so no messages are lost in spawned processes;
# create_logger() can tighten the level if the caller requests it.
_install_intercept_handlers()
_configure_logger(debug=True)


def create_logger(debug=False, log_to_file=False, disable_logging=False):
    """Return a logger compatible with the existing logging API.

    Loguru is configured with enqueue=True for multiprocessing safety —
    all log writes are serialized through a dedicated worker thread.
    """
    _install_intercept_handlers()
    _configure_logger(
        debug=debug, log_to_file=log_to_file, disable_logging=disable_logging
    )

    # Return a wrapper matching the standard logging.Logger interface
    # so existing code (logger.debug, logger.info, etc.) works unchanged.
    class _LoggerCompat:
        @staticmethod
        def debug(msg, *args, **kwargs):
            logger.debug(msg, *args, **kwargs)

        @staticmethod
        def info(msg, *args, **kwargs):
            logger.info(msg, *args, **kwargs)

        @staticmethod
        def warning(msg, *args, **kwargs):
            logger.warning(msg, *args, **kwargs)

        @staticmethod
        def error(msg, *args, **kwargs):
            logger.error(msg, *args, **kwargs)

        @staticmethod
        def exception(msg, *args, **kwargs):
            logger.exception(msg, *args, **kwargs)

        @staticmethod
        def critical(msg, *args, **kwargs):
            logger.critical(msg, *args, **kwargs)

        @staticmethod
        def setLevel(_level):
            pass

        @staticmethod
        def addHandler(_handler):
            pass

    return _LoggerCompat()
