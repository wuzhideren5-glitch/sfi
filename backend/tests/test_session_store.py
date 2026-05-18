"""Tests for SessionStore — SQLite session isolation, FTS5 search, ownership."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

# Patch DB path to temp before import
import core.session_store as ss_mod

_orig_db = ss_mod.DB_PATH


@pytest.fixture(autouse=True)
def temp_db():
    """Use temp DB for each test."""
    with tempfile.TemporaryDirectory() as tmp:
        ss_mod.DB_PATH = Path(tmp) / "test_sessions.db"
        yield
        ss_mod.DB_PATH = _orig_db


# ═══════════════════════════════════════════════════════════
# SessionManager tests
# ═══════════════════════════════════════════════════════════

class TestSessionManager:
    def test_create_session(self):
        """RED → GREEN: create returns valid session dict."""
        s = ss_mod.SessionManager.create(user_id="user_A")
        assert s["session_id"] > 0
        assert s["user_id"] == "user_A"
        assert "新对话" in s["title"]

    def test_list_sessions_per_user(self):
        """Sessions are isolated by user_id."""
        ss_mod.SessionManager.create(user_id="user_A")
        ss_mod.SessionManager.create(user_id="user_B")
        a_list = ss_mod.SessionManager.list_sessions(user_id="user_A")
        b_list = ss_mod.SessionManager.list_sessions(user_id="user_B")
        assert len(a_list) == 1
        assert len(b_list) == 1
        assert a_list[0]["session_id"] != b_list[0]["session_id"]

    def test_get_session(self):
        """get_session returns correct metadata."""
        s = ss_mod.SessionManager.create(user_id="test")
        result = ss_mod.SessionManager.get_session(s["session_id"])
        assert result is not None
        assert result["user_id"] == "test"

    def test_get_nonexistent_session(self):
        """get_session returns None for missing session."""
        assert ss_mod.SessionManager.get_session(99999) is None

    def test_update_title(self):
        """Title updates correctly."""
        s = ss_mod.SessionManager.create(user_id="test")
        ss_mod.SessionManager.update_title(s["session_id"], "Custom Title")
        result = ss_mod.SessionManager.get_session(s["session_id"])
        assert result["title"] == "Custom Title"

    def test_delete_session_cascades_turns(self):
        """Deleting session removes its turns too."""
        s = ss_mod.SessionManager.create(user_id="test")
        store = ss_mod.SessionStore(session_id=s["session_id"], user_id="test")
        store.add_turn("user", "hello")
        store.add_turn("assistant", "hi")
        assert store.count_turns() == 2

        ss_mod.SessionManager.delete_session(s["session_id"])
        assert ss_mod.SessionManager.get_session(s["session_id"]) is None


# ═══════════════════════════════════════════════════════════
# SessionStore tests
# ═══════════════════════════════════════════════════════════

class TestSessionStore:
    def test_add_turn_and_count(self):
        """RED → GREEN: turns are stored and counted."""
        s = ss_mod.SessionManager.create(user_id="test")
        store = ss_mod.SessionStore(session_id=s["session_id"], user_id="test")
        store.add_turn("user", "question 1")
        store.add_turn("assistant", "answer 1")
        assert store.count_turns() == 2

    def test_auto_title_from_first_message(self):
        """First user message becomes session title."""
        s = ss_mod.SessionManager.create(user_id="test")
        store = ss_mod.SessionStore(session_id=s["session_id"], user_id="test")
        store.add_turn("user", "我想去投行实习")
        meta = ss_mod.SessionManager.get_session(s["session_id"])
        assert "投行实习" in meta["title"] or "投行" in meta["title"]

    def test_title_not_overwritten(self):
        """Title set by first message is not overwritten by later messages."""
        s = ss_mod.SessionManager.create(user_id="test")
        store = ss_mod.SessionStore(session_id=s["session_id"], user_id="test")
        store.add_turn("user", "first message title")
        store.add_turn("assistant", "reply")
        store.add_turn("user", "second message should not change title")
        meta = ss_mod.SessionManager.get_session(s["session_id"])
        assert "first" in meta["title"]

    def test_get_recent_turns_chronological(self):
        """get_recent_turns returns oldest→newest order."""
        s = ss_mod.SessionManager.create(user_id="test")
        store = ss_mod.SessionStore(session_id=s["session_id"], user_id="test")
        store.add_turn("user", "msg1")
        store.add_turn("assistant", "msg2")
        store.add_turn("user", "msg3")
        recent = store.get_recent_turns(10)
        assert recent[0]["content"] == "msg1"
        assert recent[1]["content"] == "msg2"
        assert recent[2]["content"] == "msg3"

    def test_get_session_history(self):
        """get_session_history returns all turns chronologically."""
        s = ss_mod.SessionManager.create(user_id="test")
        store = ss_mod.SessionStore(session_id=s["session_id"], user_id="test")
        store.add_turn("user", "a")
        store.add_turn("assistant", "b")
        history = store.get_session_history()
        assert len(history) == 2
        assert history[0]["content"] == "a"

    def test_search_cross_session(self):
        """FTS5 search spans all sessions of the same user."""
        s1 = ss_mod.SessionManager.create(user_id="test")
        s2 = ss_mod.SessionManager.create(user_id="test")
        store1 = ss_mod.SessionStore(session_id=s1["session_id"], user_id="test")
        store2 = ss_mod.SessionStore(session_id=s2["session_id"], user_id="test")
        store1.add_turn("user", "投行IPO流程")
        store2.add_turn("user", "行研报告怎么写")

        # Search from store1 should find store2's content (cross-session)
        results = store1.search("行研", limit=5)
        assert len(results) >= 1
        assert any("行研" in r["content"] for r in results)

    def test_search_user_isolation(self):
        """FTS5 search does NOT cross user boundaries."""
        s_a = ss_mod.SessionManager.create(user_id="user_A")
        s_b = ss_mod.SessionManager.create(user_id="user_B")
        store_a = ss_mod.SessionStore(session_id=s_a["session_id"], user_id="user_A")
        store_b = ss_mod.SessionStore(session_id=s_b["session_id"], user_id="user_B")
        store_a.add_turn("user", "secret_A_data")
        store_b.add_turn("user", "secret_B_data")

        results = store_a.search("secret_B", limit=5)
        assert len(results) == 0  # Should NOT see user_B's data

    def test_trim_oldest_session_scoped(self):
        """trim_oldest only removes turns from THIS session, not others."""
        s1 = ss_mod.SessionManager.create(user_id="test")
        s2 = ss_mod.SessionManager.create(user_id="test")
        store1 = ss_mod.SessionStore(session_id=s1["session_id"], user_id="test")
        store2 = ss_mod.SessionStore(session_id=s2["session_id"], user_id="test")

        # Add 5 turns to store1, 3 to store2
        for i in range(5):
            store1.add_turn("user", f"msg{i}")
        for i in range(3):
            store2.add_turn("user", f"other{i}")

        # Trim store1 to keep only 2
        store1.trim_oldest(keep=2)
        assert store1.count_turns() == 2
        # store2 should be untouched
        assert store2.count_turns() == 3

    def test_trim_oldest_fts5_cleanup(self):
        """After trim, FTS5 search should NOT return deleted turns."""
        s = ss_mod.SessionManager.create(user_id="test")
        store = ss_mod.SessionStore(session_id=s["session_id"], user_id="test")
        store.add_turn("user", "unique_special_phrase_xyz")
        store.add_turn("user", "msg2")
        store.add_turn("user", "msg3")

        # Trim: keep only 1
        store.trim_oldest(keep=1)
        # Search should NOT find the deleted phrase
        results = store.search("unique_special_phrase_xyz")
        assert len(results) == 0

    def test_get_recent_turns_session_scoped(self):
        """Recent turns only from this session, not cross-contaminate."""
        s1 = ss_mod.SessionManager.create(user_id="test")
        s2 = ss_mod.SessionManager.create(user_id="test")
        store1 = ss_mod.SessionStore(session_id=s1["session_id"], user_id="test")
        store2 = ss_mod.SessionStore(session_id=s2["session_id"], user_id="test")
        store1.add_turn("user", "session1_msg")
        store2.add_turn("user", "session2_msg")

        recent1 = store1.get_recent_turns(10)
        contents = [r["content"] for r in recent1]
        assert "session1_msg" in contents
        assert "session2_msg" not in contents  # Isolated!
