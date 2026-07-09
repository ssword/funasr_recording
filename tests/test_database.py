"""Tests for the database layer — session and log CRUD."""

import sqlite3
import os
import tempfile
import pytest
from datetime import datetime

from src.database import Database


@pytest.fixture
def db():
    """Provide an isolated Database backed by an in-memory SQLite."""
    conn = sqlite3.connect(":memory:")
    db = Database(conn)
    db.initialize()
    return db


class TestSessionLifecycle:
    """Session creation, status updates, and text persistence."""

    def test_create_session_returns_row_with_defaults(self, db):
        session = db.create_session()

        assert session["id"] == 1
        assert session["status"] == "recording"
        assert session["started_at"] is not None
        assert session["ended_at"] is None
        assert session["wav_path"] is None
        assert session["live_text"] is None
        assert session["offline_text"] is None
        assert session["error_message"] is None

    def test_sequential_sessions_get_incrementing_ids(self, db):
        s1 = db.create_session()
        s2 = db.create_session()

        assert s1["id"] == 1
        assert s2["id"] == 2

    def test_update_status_to_completed_sets_ended_at(self, db):
        s = db.create_session()
        db.update_status(s["id"], "completed")
        row = db.get_session(s["id"])

        assert row["status"] == "completed"
        assert row["ended_at"] is not None

    def test_update_status_to_error_preserves_ended_at_none(self, db):
        s = db.create_session()
        db.update_status(s["id"], "error")
        row = db.get_session(s["id"])

        assert row["status"] == "error"

    def test_update_live_text(self, db):
        s = db.create_session()
        db.update_live_text(s["id"], "你好世界")
        row = db.get_session(s["id"])

        assert row["live_text"] == "你好世界"

    def test_update_offline_text(self, db):
        s = db.create_session()
        db.update_offline_text(s["id"], "你好，世界。")
        row = db.get_session(s["id"])

        assert row["offline_text"] == "你好，世界。"

    def test_set_wav_path(self, db):
        s = db.create_session()
        db.update_wav_path(s["id"], "./recordings/2026-01-01/1.wav")
        row = db.get_session(s["id"])

        assert row["wav_path"] == "./recordings/2026-01-01/1.wav"

    def test_set_error_message(self, db):
        s = db.create_session()
        db.update_error_message(s["id"], "磁盘空间不足")
        row = db.get_session(s["id"])

        assert row["error_message"] == "磁盘空间不足"


class TestLogEntries:
    """Log entry insertion and retrieval."""

    def test_log_entry_is_linked_to_session(self, db):
        s = db.create_session()
        db.insert_log(s["id"], "INFO", "WebSocket connected")
        logs = db.get_logs(s["id"])

        assert len(logs) == 1
        assert logs[0]["level"] == "INFO"
        assert logs[0]["message"] == "WebSocket connected"
        assert logs[0]["session_id"] == s["id"]

    def test_multiple_log_entries_ordered_by_timestamp(self, db):
        s = db.create_session()
        db.insert_log(s["id"], "INFO", "first")
        db.insert_log(s["id"], "WARN", "second")
        db.insert_log(s["id"], "ERROR", "third")
        logs = db.get_logs(s["id"])

        assert [l["message"] for l in logs] == ["first", "second", "third"]

    def test_get_logs_for_nonexistent_session_returns_empty(self, db):
        logs = db.get_logs(999)
        assert logs == []

    def test_completed_and_error_sessions_are_distinguishable(self, db):
        s1 = db.create_session()
        db.update_status(s1["id"], "completed")
        s2 = db.create_session()
        db.update_status(s2["id"], "error")

        assert db.get_session(s1["id"])["status"] == "completed"
        assert db.get_session(s2["id"])["status"] == "error"
