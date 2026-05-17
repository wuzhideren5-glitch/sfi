"""Session storage — SQLite + FTS5 full-text search, inspired by Hermes state.db.
Replaces JSON-based personal KB with a robust, searchable session store.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "personal_kb" / "sessions.db"
DB_PATH.parent.mkdir(exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            started_at REAL,
            updated_at REAL
        );

        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT NOT NULL,         -- 'user' or 'assistant'
            content TEXT NOT NULL,
            embedding BLOB,             -- 1024-dim float32 vector
            created_at REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
            content,
            tokenize='trigram'          -- CJK-friendly trigram tokenizer
        );

        CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
        CREATE INDEX IF NOT EXISTS idx_turns_created ON turns(created_at);
    """)
    conn.commit()
    conn.close()


class SessionStore:
    """Manages conversation turns with SQLite storage + FTS5 search."""

    def __init__(self):
        init_db()
        self._session_id = self._get_or_create_session()

    def _get_or_create_session(self) -> int:
        conn = _get_conn()
        row = conn.execute(
            "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row:
            conn.close()
            return row["id"]

        now = time.time()
        cur = conn.execute(
            "INSERT INTO sessions (started_at, updated_at) VALUES (?, ?)",
            (now, now),
        )
        sid = cur.lastrowid
        conn.commit()
        conn.close()
        return sid

    def add_turn(self, role: str, content: str, embedding: list[float] | None = None):
        conn = _get_conn()
        now = time.time()
        emb_bytes = None
        if embedding:
            import numpy as np
            emb_bytes = np.array(embedding, dtype=np.float32).tobytes()

        cur = conn.execute(
            "INSERT INTO turns (session_id, role, content, embedding, created_at) VALUES (?, ?, ?, ?, ?)",
            (self._session_id, role, content, emb_bytes, now),
        )
        turn_id = cur.lastrowid

        # Insert into FTS5 index
        conn.execute(
            "INSERT INTO turns_fts (rowid, content) VALUES (?, ?)",
            (turn_id, content),
        )

        # Update session timestamp
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, self._session_id))
        conn.commit()
        conn.close()

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """FTS5 full-text search across all conversation turns.

        For short CJK queries (< 3 chars) the trigram tokenizer can't match,
        so we fall back to SQLite LIKE.
        """
        conn = _get_conn()
        # Detect short CJK query: count CJK chars, if < 3 use LIKE fallback
        cjk_count = sum(1 for c in query if '\u4e00' <= c <= '\u9fff')
        if cjk_count < 3:
            like_query = f"%{query}%"
            rows = conn.execute(
                "SELECT role, content, created_at FROM turns WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (like_query, limit),
            ).fetchall()
        else:
            try:
                rows = conn.execute(
                    """SELECT t.role, t.content, t.created_at
                       FROM turns_fts fts
                       JOIN turns t ON t.id = fts.rowid
                       WHERE turns_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        conn.close()
        return [{"role": r["role"], "content": r["content"], "ts": r["created_at"]} for r in rows]

    def get_recent_turns(self, n: int = 30) -> list[dict]:
        """Get most recent conversation turns."""
        conn = _get_conn()
        rows = conn.execute(
            "SELECT role, content FROM turns ORDER BY created_at DESC LIMIT ?",
            (n,),
        ).fetchall()
        conn.close()
        # Return in chronological order
        result = []
        for r in reversed(rows):
            result.append({"role": r["role"], "content": r["content"]})
        return result

    def count_turns(self) -> int:
        conn = _get_conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM turns").fetchone()
        conn.close()
        return row["cnt"] if row else 0

    def trim_oldest(self, keep: int = 200):
        """Auto-prune: delete oldest turns when total exceeds keep count.
        Hermes design: prevents unbounded DB growth, keeps memory fresh."""
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        if total <= keep:
            conn.close()
            return 0

        # Delete oldest turns, keeping the most recent `keep` turns
        cutoff_id = conn.execute(
            "SELECT id FROM turns ORDER BY id DESC LIMIT 1 OFFSET ?",
            (keep,),
        ).fetchone()

        if cutoff_id:
            deleted = conn.execute(
                "DELETE FROM turns WHERE id <= ?", (cutoff_id["id"],)
            ).rowcount
            # Also clean FTS5 index
            conn.execute("DELETE FROM turns_fts WHERE rowid <= ?", (cutoff_id["id"],))
            conn.commit()
            conn.close()
            return deleted

        conn.close()
        return 0
