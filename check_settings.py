import sqlite3
import os

db_path = "tobacco_management.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        rows = cursor.execute("SELECT * FROM system_settings").fetchall()
        for row in rows:
            print(f"{row['key']}: {row['value']}")
    except Exception as e:
        print(f"Error: {e}")
    conn.close()
else:
    print("DB not found")
