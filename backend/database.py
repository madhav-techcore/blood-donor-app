import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "blood_donor.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS donors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            blood_type TEXT NOT NULL,
            city TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
