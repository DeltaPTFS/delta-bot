"""Small, durable SQLite-backed economy used by the Discord commands."""

from __future__ import annotations

import random
import sqlite3
import threading
import time
from pathlib import Path


class EconomyStore:
    """Store balances and cooldowns safely across bot restarts."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS economy (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0,
                    daily_at INTEGER NOT NULL DEFAULT 0,
                    work_at INTEGER NOT NULL DEFAULT 0
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def balance(self, user_id: int) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT balance FROM economy WHERE user_id = ?", (user_id,)
            ).fetchone()
            return int(row[0]) if row else 0

    def claim(self, user_id: int, kind: str, cooldown: int, low: int, high: int) -> tuple[int, int]:
        """Claim a randomized reward, returning ``(reward, seconds_remaining)``."""
        if kind not in {"daily", "work"}:
            raise ValueError("Unknown economy reward type.")
        column = f"{kind}_at"
        now = int(time.time())
        with self._lock, self._connect() as connection:
            connection.execute("INSERT OR IGNORE INTO economy (user_id) VALUES (?)", (user_id,))
            last_claim = int(connection.execute(
                f"SELECT {column} FROM economy WHERE user_id = ?", (user_id,)
            ).fetchone()[0])
            remaining = cooldown - (now - last_claim)
            if remaining > 0:
                return 0, remaining
            reward = random.randint(low, high)
            connection.execute(
                f"UPDATE economy SET balance = balance + ?, {column} = ? WHERE user_id = ?",
                (reward, now, user_id),
            )
            return reward, 0

    def transfer(self, sender_id: int, recipient_id: int, amount: int) -> bool:
        if amount <= 0 or sender_id == recipient_id:
            return False
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT OR IGNORE INTO economy (user_id) VALUES (?)", (sender_id,))
            connection.execute("INSERT OR IGNORE INTO economy (user_id) VALUES (?)", (recipient_id,))
            updated = connection.execute(
                "UPDATE economy SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                (amount, sender_id, amount),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return False
            connection.execute(
                "UPDATE economy SET balance = balance + ? WHERE user_id = ?",
                (amount, recipient_id),
            )
            return True

    def leaderboard(self, limit: int = 10) -> list[tuple[int, int]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT user_id, balance FROM economy ORDER BY balance DESC, user_id ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(int(user_id), int(balance)) for user_id, balance in rows]
