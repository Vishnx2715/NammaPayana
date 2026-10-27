"""Shared SQLite connection helper for Namma Payana."""
import sqlite3
import contextlib
from typing import Generator
import config

def get_connection(db_path: str = None) -> sqlite3.Connection:
    path = db_path or config.DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextlib.contextmanager
def db_connection(db_path: str = None) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()
