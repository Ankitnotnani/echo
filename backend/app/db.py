"""SQLite session storage.

One short-lived connection per operation keeps this safe across FastAPI's
thread pool. A turn (user + assistant rows, session upsert) is written in a
single transaction, and only after the LLM succeeded, so a failed request
(422 / 503) never leaves anything behind.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    metadata    TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, id);

CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    system_prompt TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def init(self) -> None:
        """Create the parent folder and schema. Safe to call on every startup."""
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
            conn.commit()

    def ping(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute("SELECT 1").fetchone()

    def load_context(self, session_id: str, limit: int) -> tuple[Optional[str], list[dict[str, str]]]:
        """Return (stored system prompt, last `limit` messages oldest-first)."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT system_prompt FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            stored_prompt = row["system_prompt"] if row else None
            if limit <= 0:
                return stored_prompt, []
            rows = conn.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content FROM messages
                    WHERE session_id = ? ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
                """,
                (session_id, limit),
            ).fetchall()
        history = [{"role": r["role"], "content": r["content"]} for r in rows]
        # A truncated window must still start with a user turn for some providers.
        while history and history[0]["role"] != "user":
            history.pop(0)
        return stored_prompt, history

    def save_turn(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        metadata: dict[str, Any],
        system_prompt: Optional[str],
        user_created_at: str,
    ) -> None:
        now = utc_now_iso()
        with closing(self._connect()) as conn:
            with conn:  # one transaction: all three writes or none
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, system_prompt, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        system_prompt = COALESCE(excluded.system_prompt, sessions.system_prompt),
                        updated_at = excluded.updated_at
                    """,
                    (session_id, system_prompt, user_created_at, now),
                )
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, metadata, created_at) "
                    "VALUES (?, 'user', ?, NULL, ?)",
                    (session_id, user_content, user_created_at),
                )
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, metadata, created_at) "
                    "VALUES (?, 'assistant', ?, ?, ?)",
                    (session_id, assistant_content, json.dumps(metadata), now),
                )

    def list_messages(self, session_id: str) -> Optional[list[dict[str, Any]]]:
        """Full history oldest-first, or None when the session does not exist."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT role, content, metadata, created_at FROM messages "
                "WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        if not rows:
            return None
        out: list[dict[str, Any]] = []
        for r in rows:
            item: dict[str, Any] = {"role": r["role"], "content": r["content"]}
            if r["role"] == "assistant" and r["metadata"]:
                try:
                    item["metadata"] = json.loads(r["metadata"])
                except json.JSONDecodeError:
                    item["metadata"] = {}
            item["created_at"] = r["created_at"]
            out.append(item)
        return out
