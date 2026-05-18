"""Session storage — SQLite + FTS5, multi-user + multi-session support.
Each user has isolated sessions. Memory is cross-session per user.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "personal_kb" / "sessions.db"
DB_PATH.parent.mkdir(exist_ok=True)

TEST_USER_ID = "user_test_001"  # 内测阶段固定用户

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default',
            title TEXT DEFAULT '',
            started_at REAL,
            updated_at REAL
        );

        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB,
            created_at REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
            content,
            tokenize='trigram'
        );

        CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
        CREATE INDEX IF NOT EXISTS idx_turns_created ON turns(created_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at);
    """)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════
# Session Manager — handles session lifecycle
# ═══════════════════════════════════════════════════════════

class SessionManager:
    """Create, list, delete sessions per user."""

    @staticmethod
    def create(user_id: str = TEST_USER_ID, title: str = "") -> dict:
        conn = _get_conn()
        now = time.time()
        cur = conn.execute(
            "INSERT INTO sessions (user_id, title, started_at, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, title, now, now),
        )
        sid = cur.lastrowid
        conn.commit()
        conn.close()
        return {"session_id": sid, "user_id": user_id, "title": title or "新对话", "created_at": now}

    @staticmethod
    def list_sessions(user_id: str = TEST_USER_ID) -> list[dict]:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT s.id, s.title, s.started_at, s.updated_at,
                      COUNT(t.id) as turn_count
               FROM sessions s
               LEFT JOIN turns t ON t.session_id = s.id
               WHERE s.user_id = ?
               GROUP BY s.id
               ORDER BY s.updated_at DESC""",
            (user_id,),
        ).fetchall()
        conn.close()
        return [
            {
                "session_id": r["id"],
                "title": r["title"] or "新对话",
                "started_at": r["started_at"],
                "updated_at": r["updated_at"],
                "turn_count": r["turn_count"] or 0,
            }
            for r in rows
        ]

    @staticmethod
    def update_title(session_id: int, title: str):
        conn = _get_conn()
        conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_session(session_id: int) -> dict | None:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)

    @staticmethod
    def delete_session(session_id: int):
        conn = _get_conn()
        conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()


# ═══════════════════════════════════════════════════════════
# SessionStore — scoped to a single session
# ═══════════════════════════════════════════════════════════

class SessionStore:
    """Manages turns within one session. Search is user-scoped (cross-session)."""

    def __init__(self, session_id: int, user_id: str = TEST_USER_ID):
        init_db()
        self.session_id = session_id
        self.user_id = user_id

    def add_turn(self, role: str, content: str, embedding: list[float] | None = None):
        conn = _get_conn()
        now = time.time()
        emb_bytes = None
        if embedding:
            import numpy as np
            emb_bytes = np.array(embedding, dtype=np.float32).tobytes()

        cur = conn.execute(
            "INSERT INTO turns (session_id, role, content, embedding, created_at) VALUES (?, ?, ?, ?, ?)",
            (self.session_id, role, content, emb_bytes, now),
        )
        turn_id = cur.lastrowid

        conn.execute(
            "INSERT INTO turns_fts (rowid, content) VALUES (?, ?)",
            (turn_id, content),
        )

        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, self.session_id))

        # Auto-title: use first user message as session title
        if role == "user":
            title_row = conn.execute("SELECT title FROM sessions WHERE id = ?", (self.session_id,)).fetchone()
            if title_row and (not title_row["title"] or title_row["title"] == "新对话"):
                title = content[:30].replace("\n", " ")
                conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, self.session_id))

        conn.commit()
        conn.close()

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """FTS5 search across ALL sessions of this user (cross-session memory)."""
        conn = _get_conn()
        cjk_count = sum(1 for c in query if '\u4e00' <= c <= '\u9fff')

        if cjk_count < 3:
            like_query = f"%{query}%"
            rows = conn.execute(
                """SELECT t.role, t.content, t.created_at, s.id as sid
                   FROM turns t JOIN sessions s ON t.session_id = s.id
                   WHERE s.user_id = ? AND t.content LIKE ?
                   ORDER BY t.created_at DESC LIMIT ?""",
                (self.user_id, like_query, limit),
            ).fetchall()
        else:
            try:
                rows = conn.execute(
                    """SELECT t.role, t.content, t.created_at, s.id as sid
                       FROM turns_fts fts
                       JOIN turns t ON t.id = fts.rowid
                       JOIN sessions s ON t.session_id = s.id
                       WHERE s.user_id = ? AND turns_fts MATCH ?
                       ORDER BY rank LIMIT ?""",
                    (self.user_id, query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

        conn.close()
        return [{"role": r["role"], "content": r["content"], "ts": r["created_at"], "session_id": r["sid"]} for r in rows]

    def get_recent_turns(self, n: int = 30) -> list[dict]:
        """Get most recent turns in THIS session only."""
        conn = _get_conn()
        rows = conn.execute(
            "SELECT role, content FROM turns WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (self.session_id, n),
        ).fetchall()
        conn.close()
        result = []
        for r in reversed(rows):
            result.append({"role": r["role"], "content": r["content"]})
        return result

    def get_session_history(self) -> list[dict]:
        """Get ALL turns in this session (for frontend)."""
        conn = _get_conn()
        rows = conn.execute(
            "SELECT role, content, created_at FROM turns WHERE session_id = ? ORDER BY created_at ASC",
            (self.session_id,),
        ).fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"], "ts": r["created_at"]} for r in rows]

    def count_turns(self) -> int:
        conn = _get_conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM turns WHERE session_id = ?", (self.session_id,)).fetchone()
        conn.close()
        return row["cnt"] if row else 0

    def trim_oldest(self, keep: int = 200):
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM turns WHERE session_id = ?", (self.session_id,)).fetchone()[0]
        if total <= keep:
            conn.close()
            return 0

        cutoff = conn.execute(
            "SELECT id FROM turns WHERE session_id = ? ORDER BY id DESC LIMIT 1 OFFSET ?",
            (self.session_id, keep),
        ).fetchone()

        if cutoff:
            # Get the IDs we're actually deleting (session-scoped)
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM turns WHERE session_id = ? AND id <= ?",
                (self.session_id, cutoff["id"]),
            ).fetchall()]
            if ids:
                placeholders = ",".join("?" * len(ids))
                conn.execute(f"DELETE FROM turns WHERE id IN ({placeholders})", ids)
                conn.execute(f"DELETE FROM turns_fts WHERE rowid IN ({placeholders})", ids)
                deleted = len(ids)
            else:
                deleted = 0
            conn.commit()
            conn.close()
            return deleted
        conn.close()
        return 0
