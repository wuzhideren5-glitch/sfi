"""Personal Knowledge Base — stores user conversation history as vectors.
Every turn is embedded, stored, and retrievable via RAG on subsequent queries.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from core.embedding import embed_single

STORAGE_DIR = Path(__file__).parent.parent / "personal_kb"
STORAGE_DIR.mkdir(exist_ok=True)
MEMORY_FILE = STORAGE_DIR / "memory.json"
EMBEDDINGS_FILE = STORAGE_DIR / "embeddings.npy"


class PersonalKB:
    """User's personal conversation memory with vector RAG retrieval."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._memories: list[dict] = []
        self._embeddings: np.ndarray | None = None
        self._load()

    def _load(self):
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE) as f:
                self._memories = json.load(f)
        if EMBEDDINGS_FILE.exists():
            self._embeddings = np.load(EMBEDDINGS_FILE)
        else:
            self._embeddings = np.empty((0, 1024))

    def _save(self):
        with open(MEMORY_FILE, "w") as f:
            json.dump(self._memories, f, ensure_ascii=False, indent=2)
        np.save(EMBEDDINGS_FILE, self._embeddings)

    def add_turn(self, user_msg: str, ai_reply: str):
        """Store a conversation turn as a vectorized memory."""
        text = f"用户：{user_msg}\nAI：{ai_reply}"
        try:
            vec = embed_single(text)
            vec = np.array(vec, dtype=np.float32)
        except Exception:
            return

        memory = {
            "user": user_msg,
            "ai": ai_reply,
            "ts": time.time(),
        }
        self._memories.append(memory)

        if self._embeddings is None or self._embeddings.size == 0:
            self._embeddings = vec.reshape(1, -1)
        else:
            self._embeddings = np.vstack([self._embeddings, vec.reshape(1, -1)])

        # Keep only last 200 turns
        if len(self._memories) > 200:
            self._memories = self._memories[-200:]
            self._embeddings = self._embeddings[-200:]

        self._save()

    def search(self, query: str, top_k: int = 5) -> str:
        """RAG: search personal KB for relevant past conversations."""
        if self._embeddings is None or self._embeddings.size == 0:
            return ""

        try:
            q_vec = np.array(embed_single(query), dtype=np.float32)
        except Exception:
            return ""

        # Cosine similarity
        q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-8)
        db_norm = self._embeddings / (np.linalg.norm(self._embeddings, axis=1, keepdims=True) + 1e-8)
        scores = np.dot(db_norm, q_norm)

        top_indices = np.argsort(scores)[-top_k:][::-1]

        lines = []
        for idx in top_indices:
            if scores[idx] < 0.3:  # Relevance threshold
                continue
            m = self._memories[idx]
            lines.append(f"[历史对话 {idx}] 用户问：{m['user'][:200]}\nAI答：{m['ai'][:300]}")

        return "\n\n".join(lines) if lines else ""

    def get_recent_history(self, n: int = 10) -> list[dict]:
        """Get recent conversation history for the agent context."""
        recent = self._memories[-n:]
        history = []
        for m in recent:
            history.append({"role": "user", "content": m["user"]})
            history.append({"role": "assistant", "content": m["ai"]})
        return history
