"""SQLite persistence for recording sessions and log entries."""

import sqlite3
from datetime import datetime, timezone


class Database:
    """Manages the sessions and log_entries tables in SQLite.

    Supports in-memory (`:memory:`) for testing and file-backed for production.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row

    def initialize(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                status TEXT NOT NULL DEFAULT 'recording',
                wav_path TEXT,
                live_text TEXT,
                offline_text TEXT,
                error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            );
        """)
        self._conn.commit()

    # ── Sessions ────────────────────────────────────────────────────────────

    def create_session(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO sessions (started_at) VALUES (?)", (now,)
        )
        self._conn.commit()
        assert cur.lastrowid is not None
        row = self.get_session(cur.lastrowid)
        assert row is not None
        return dict(row)

    def get_session(self, session_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_status(self, session_id: int, status: str) -> None:
        if status in ("completed", "error"):
            now = datetime.now(timezone.utc).isoformat()
            self._conn.execute(
                "UPDATE sessions SET status = ?, ended_at = ? WHERE id = ?",
                (status, now, session_id),
            )
        else:
            self._conn.execute(
                "UPDATE sessions SET status = ? WHERE id = ?", (status, session_id)
            )
        self._conn.commit()

    def update_live_text(self, session_id: int, text: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET live_text = ? WHERE id = ?", (text, session_id)
        )
        self._conn.commit()

    def update_offline_text(self, session_id: int, text: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET offline_text = ? WHERE id = ?", (text, session_id)
        )
        self._conn.commit()

    def update_wav_path(self, session_id: int, path: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET wav_path = ? WHERE id = ?", (path, session_id)
        )
        self._conn.commit()

    def update_error_message(self, session_id: int, message: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET error_message = ? WHERE id = ?",
            (message, session_id),
        )
        self._conn.commit()

    # ── Log entries ─────────────────────────────────────────────────────────

    def insert_log(self, session_id: int, level: str, message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO log_entries (session_id, timestamp, level, message) "
            "VALUES (?, ?, ?, ?)",
            (session_id, now, level, message),
        )
        self._conn.commit()

    def get_logs(self, session_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM log_entries WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
