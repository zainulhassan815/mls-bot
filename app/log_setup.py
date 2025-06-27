import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logger(
    info_log_path="logs/info.log",
    error_log_path="logs/error.log",
    max_bytes=1000000,
    backup_count=3,
):
    """
    Sets up and returns a configured logger instance.

    - Creates rotating file handlers for info and error logs.
    - Filters logs so only INFO logs go to info.log and ERROR or higher go to error.log.
    - Also logs DEBUG+ to console (stream handler).
    - Ensures log directories exist.

    Args:
        info_log_path (str): Path to the info log file.
        error_log_path (str): Path to the error log file.
        max_bytes (int): Max size in bytes before rotating a log file.
        backup_count (int): Number of backup log files to keep.

    Returns:
        logging.Logger: Configured logger instance.
    """

    if not os.path.exists("logs"):
        os.mkdir("logs")

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    info_handler = RotatingFileHandler(
        info_log_path, maxBytes=max_bytes, backupCount=backup_count
    )
    info_handler.setLevel(logging.INFO)
    info_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    info_handler.setFormatter(info_format)

    error_handler = RotatingFileHandler(
        error_log_path, maxBytes=max_bytes, backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    error_handler.setFormatter(error_format)

    class InfoFilter(logging.Filter):
        def filter(self, record):
            return record.levelno == logging.INFO

    class ErrorFilter(logging.Filter):
        def filter(self, record):
            return record.levelno >= logging.ERROR

    info_handler.addFilter(InfoFilter())
    error_handler.addFilter(ErrorFilter())

    logger.addHandler(info_handler)
    logger.addHandler(error_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(info_format)
    logger.addHandler(stream_handler)

    return logger
