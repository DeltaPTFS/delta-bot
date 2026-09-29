"""Durable event counters used to produce the weekly moderation digest."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path


class AuditLogStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS audit_metadata (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def record(self, event_type: str, created_at: int | None = None) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_events (event_type, created_at) VALUES (?, ?)",
                (event_type, created_at if created_at is not None else int(time.time())),
            )

    def counts(self, start: int, end: int) -> Counter[str]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT event_type, COUNT(*) FROM audit_events
                   WHERE created_at >= ? AND created_at < ? GROUP BY event_type""",
                (start, end),
            ).fetchall()
        return Counter({str(event_type): int(count) for event_type, count in rows})

    def last_report(self) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM audit_metadata WHERE key = 'last_weekly_report'"
            ).fetchone()
            return int(row[0]) if row else 0

    def mark_reported(self, boundary: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO audit_metadata (key, value) VALUES ('last_weekly_report', ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (boundary,),
            )
            # Detailed Discord logs remain in Discord; retain eight weeks of
            # counters locally so this database never grows without bound.
            connection.execute(
                "DELETE FROM audit_events WHERE created_at < ?", (boundary - 8 * 604_800,)
            )
