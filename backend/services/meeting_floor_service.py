"""
Central moderation for multi-agent Realtime meeting: one floor, human barge-in, score-based interrupt.

State is in-process (per Flask worker). For multi-worker deployments use Redis with the same API.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# Higher → easier to take floor from current holder (when not human speaking)
INTERRUPT_DELTA = float(os.getenv("MEETING_FLOOR_INTERRUPT_DELTA", "0.12"))


@dataclass
class _FloorState:
    human_active: bool = False
    holder: Optional[str] = None
    holder_score: float = 0.0
    updated_at: float = field(default_factory=time.monotonic)


_lock = threading.Lock()
# session_id -> _FloorState
_sessions: Dict[str, _FloorState] = {}


def _get_or_create(session_id: str) -> _FloorState:
    if session_id not in _sessions:
        _sessions[session_id] = _FloorState()
    return _sessions[session_id]


def set_human_active(session_id: str, active: bool) -> None:
    """Human mic VAD: when True, deny all agent floor requests until False."""
    with _lock:
        s = _get_or_create(session_id)
        s.human_active = bool(active)
        if active:
            s.holder = None
            s.holder_score = 0.0
        s.updated_at = time.monotonic()


def release_holder(session_id: str, agent_id: str) -> None:
    """Call when agent finishes a response (response.done)."""
    agent_id = (agent_id or "").strip()
    session_id = (session_id or "").strip()
    with _lock:
        if session_id not in _sessions:
            return
        s = _sessions[session_id]
        if s.holder == agent_id:
            s.holder = None
            s.holder_score = 0.0
        s.updated_at = time.monotonic()


def clear_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


def request_floor(session_id: str, agent_id: str, score: float) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Request permission to start a new assistant response (after client cancelled auto response).

    - If human is speaking: always deny.
    - If no holder: grant and set holder.
    - If same holder: grant (continuation / second response.create).
    - Else: grant only if score >= holder_score + INTERRUPT_DELTA (replace holder).
    """
    agent_id = (agent_id or "").strip()
    session_id = (session_id or "").strip()
    score = max(0.0, min(1.0, float(score)))
    with _lock:
        s = _get_or_create(session_id)
        s.updated_at = time.monotonic()
        if s.human_active:
            return False, "human_active", {"holder": None, "human_active": True}

        if s.holder is None:
            s.holder = agent_id
            s.holder_score = score
            return True, "open_floor", {"holder": agent_id, "score": score}

        if s.holder == agent_id:
            s.holder_score = max(s.holder_score, score)
            return True, "same_holder", {"holder": agent_id, "score": s.holder_score}

        if score >= s.holder_score + INTERRUPT_DELTA:
            s.holder = agent_id
            s.holder_score = score
            return True, "interrupt", {"holder": agent_id, "score": score}

        return False, "lower_priority", {"holder": s.holder, "score": s.holder_score}


def snapshot(session_id: str) -> Dict[str, Any]:
    with _lock:
        if session_id not in _sessions:
            return {"human_active": False, "holder": None}
        s = _sessions[session_id]
        return {
            "human_active": s.human_active,
            "holder": s.holder,
            "holder_score": s.holder_score,
        }
