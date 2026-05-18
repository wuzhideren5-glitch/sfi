"""MemoryManager — Hermes-style memory orchestration: prefetch → inject → sync.
Session-scoped: each session gets its own MemoryManager.
Cross-session search: FTS5 searches all sessions of the same user.
"""
from __future__ import annotations

from core.embedding import embed_single
from core.session_store import SessionStore

MEMORY_FENCE_OPEN = (
    "<memory-context>\n"
    "[System note: The following is recalled memory context, NOT new user input.\n"
    "Treat as authoritative reference data. Do not respond to it as a new message.]"
)
MEMORY_FENCE_CLOSE = "</memory-context>"


class MemoryManager:
    """Orchestrates memory lifecycle scoped to a session."""

    def __init__(self, session_id: int, user_id: str = "user_test_001"):
        self._store = SessionStore(session_id=session_id, user_id=user_id)

    def prefetch(self, user_message: str) -> str:
        """Cross-session FTS5 recall for the current user."""
        results = self._store.search(user_message, limit=5)
        if not results:
            return ""

        lines = []
        for r in results:
            role_label = "学生" if r["role"] == "user" else "小苗老师"
            session_tag = f"[会话{r['session_id']}]" if r.get("session_id") else ""
            lines.append(f"{session_tag}[{role_label}]：{r['content'][:300]}")

        context = "\n".join(lines)
        return f"{MEMORY_FENCE_OPEN}\n{context}\n{MEMORY_FENCE_CLOSE}"

    def sync(self, user_message: str, assistant_reply: str):
        try:
            emb = embed_single(f"{user_message}\n{assistant_reply}")
        except Exception:
            emb = None

        self._store.add_turn("user", user_message, emb)
        self._store.add_turn("assistant", assistant_reply, None)
        self._store.trim_oldest(keep=200)

    def get_recent_history(self, n: int = 30) -> list[dict]:
        return self._store.get_recent_turns(n)

    def get_memory_count(self) -> int:
        return self._store.count_turns()

    def get_full_history(self) -> list[dict]:
        return self._store.get_session_history()
