import sqlite3
import os
import time
from typing import Optional, List
from .utils import logger

class SqliteStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
        self._init_db()
        logger.info(f"Using SQLite storage: {db_path}")

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at INTEGER NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_at 
            ON processed_messages(processed_at)
        """)
        conn.commit()

    def has_processed(self, message_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,))
        return cursor.fetchone() is not None

    def mark_processed(self, message_id: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
            (message_id, int(time.time() * 1000))
        )
        conn.commit()
        logger.debug(f"Marked as processed (SQLite): {message_id}")

    def cleanup(self, older_than_days: int = 30):
        cutoff = int((time.time() - (older_than_days * 24 * 60 * 60)) * 1000)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processed_messages WHERE processed_at < ?", (cutoff,))
        changes = conn.total_changes
        conn.commit()
        logger.info(f"Cleaned up {changes} old entries")

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

storage_impl: Optional[SqliteStorage] = None

def init_storage() -> SqliteStorage:
    global storage_impl
    if storage_impl:
        return storage_impl

    db_path = os.getenv('PROCESSED_STORE_SQLITE', './data/processed.db')
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    storage_impl = SqliteStorage(db_path)
    return storage_impl

def has_processed(message_id: str) -> bool:
    if not storage_impl:
        raise RuntimeError("Storage not initialized. Call init_storage() first.")
    return storage_impl.has_processed(message_id)

def mark_processed(message_id: str):
    if not storage_impl:
        raise RuntimeError("Storage not initialized. Call init_storage() first.")
    storage_impl.mark_processed(message_id)

def cleanup(older_than_days: int = 30):
    if storage_impl:
        storage_impl.cleanup(older_than_days)

def close_storage():
    global storage_impl
    if storage_impl:
        storage_impl.close()
        storage_impl = None
