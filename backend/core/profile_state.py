"""Shared user profile state — read by chat, written by parser."""
from __future__ import annotations

from typing import Any, Dict

# Module-level profile store (single user for demo)
_current_profile: Dict[str, Any] = {}


def get_profile() -> Dict[str, Any]:
    return _current_profile


def set_profile(profile: Dict[str, Any]):
    global _current_profile
    _current_profile = profile
