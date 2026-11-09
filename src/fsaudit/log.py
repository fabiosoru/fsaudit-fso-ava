"""Logging vers la console et vers un fichier .log."""

import logging


def setup_logging(log_file: str, level: str = "INFO") -> None:
    logger = logging.getLogger("fsaudit")
    logger.setLevel(level.upper())
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
