"""MemoryManager — Hermes-style memory orchestration: prefetch → inject → sync.
Implements Memory Fencing to prevent LLM from confusing memories with new input.
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
    """Orchestrates memory lifecycle: prefetch before turn, sync after turn."""

    def __init__(self):
        self._store = SessionStore()

    def prefetch(self, user_message: str) -> str:
        """
        Called BEFORE each agent turn.
        Returns formatted memory context to inject into system prompt.
        Uses FTS5 full-text search for relevant past turns.
        """
        # FTS5 search for related history
        results = self._store.search(user_message, limit=5)
        if not results:
            return ""

        lines = []
        for r in results:
            role_label = "学生" if r["role"] == "user" else "小苗老师"
            lines.append(f"[{role_label}]：{r['content'][:300]}")

        context = "\n".join(lines)
        return f"{MEMORY_FENCE_OPEN}\n{context}\n{MEMORY_FENCE_CLOSE}"

    def sync(self, user_message: str, assistant_reply: str):
        """
        Called AFTER each agent turn.
        Persists the turn to SQLite and generates embedding for the pair.
        """
        # Store both turns
        try:
            emb = embed_single(f"{user_message}\n{assistant_reply}")
        except Exception:
            emb = None

        self._store.add_turn("user", user_message, emb)
        self._store.add_turn("assistant", assistant_reply, None)

        # Auto-prune old turns when exceeding threshold (Hermes: unbounded growth prevention)
        self._store.trim_oldest(keep=200)

    def get_recent_history(self, n: int = 30) -> list[dict]:
        """Get most recent turns for forced context injection."""
        return self._store.get_recent_turns(n)

    def get_memory_count(self) -> int:
        """Total stored turns (half = conversation rounds)."""
        return self._store.count_turns()
