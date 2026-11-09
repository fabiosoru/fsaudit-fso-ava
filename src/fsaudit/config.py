"""Configuration : valeurs par défaut, surchargées par un fichier JSON puis par l'env."""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    db_path: str = "fsaudit.db"
    log_file: str = "fsaudit.log"
    log_level: str = "INFO"


def load_config(config_file: str = "fsaudit.json") -> Config:
    """Charge la config : défauts < fichier JSON < variables d'environnement."""
    config = Config()

    path = Path(config_file)
    if path.is_file():
        data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
        config.db_path = data.get("db_path", config.db_path)
        config.log_file = data.get("log_file", config.log_file)
        config.log_level = data.get("log_level", config.log_level)

    config.db_path = os.environ.get("FSAUDIT_DB", config.db_path)
    config.log_file = os.environ.get("FSAUDIT_LOG_FILE", config.log_file)
    config.log_level = os.environ.get("FSAUDIT_LOG_LEVEL", config.log_level)
    return config
