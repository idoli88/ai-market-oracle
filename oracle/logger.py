import logging
import sys
from oracle.config import settings

def setup_logger(name: str) -> logging.Logger:
    """
    Configure and return a logger instance.
    """
    logger = logging.getLogger(name)

    # Prevent adding multiple handlers if setup is called multiple times
    if logger.hasHandlers():
        return logger

    logger.setLevel(settings.LOG_LEVEL.upper())

    # Console Handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(settings.LOG_LEVEL.upper())

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger
