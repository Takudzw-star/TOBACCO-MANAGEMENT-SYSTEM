import sqlite3
import os
from pathlib import Path

default_db_path = Path(__file__).resolve().parents[1] / "tobacco_management.db"
render_db_path = "/var/data/tobacco_management.db"
DB_PATH = os.environ.get(
    "DB_PATH",
    render_db_path if os.environ.get("RENDER") else str(default_db_path),
)
_ACTIVE_DB_PATH = None


def get_db_path() -> str:
    global _ACTIVE_DB_PATH
    if _ACTIVE_DB_PATH:
        return _ACTIVE_DB_PATH

    preferred = Path(DB_PATH)
    fallback = Path(default_db_path)

    for candidate in (preferred, fallback):
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            _ACTIVE_DB_PATH = str(candidate)
            return _ACTIVE_DB_PATH
        except OSError:
            continue

    # Last resort: let sqlite try current working directory
    _ACTIVE_DB_PATH = str(fallback)
    return _ACTIVE_DB_PATH


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

