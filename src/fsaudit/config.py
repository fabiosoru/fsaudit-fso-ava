"""Configuration : valeurs par défaut, remplacées par les variables d'environnement."""

import os

DB_PATH = os.environ.get("FSAUDIT_DB", "fsaudit.db")
LOG_FILE = os.environ.get("FSAUDIT_LOG_FILE", "fsaudit.log")
LOG_LEVEL = os.environ.get("FSAUDIT_LOG_LEVEL", "INFO")
