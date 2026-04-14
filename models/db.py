import sqlite3
import os
from pathlib import Path

default_db_path = Path(__file__).resolve().parents[1] / "tobacco_management.db"
render_db_path = "/var/data/tobacco_management.db"
DB_PATH = os.environ.get(
    "DB_PATH",
    render_db_path if os.environ.get("RENDER") else str(default_db_path),
)


def get_connection():
    db_file = Path(DB_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

