"""HTTP API for meeting floor moderation (multi-agent Realtime)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from services import meeting_floor_service as floor

meeting_floor_bp = Blueprint("meeting_floor", __name__)


@meeting_floor_bp.route("/api/meeting/floor/human", methods=["POST"])
def meeting_floor_human():
    """Body: { session_id, active: bool } — human mic speech started/stopped."""
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    active = bool(data.get("active"))
    floor.set_human_active(session_id, active)
    return jsonify({"ok": True, **floor.snapshot(session_id)})


@meeting_floor_bp.route("/api/meeting/floor/request", methods=["POST"])
def meeting_floor_request():
    """
    Body: { session_id, agent_participant_id, score: float in [0,1] }
    Returns: { granted, reason, ... }
    """
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    agent_id = (data.get("agent_participant_id") or data.get("agent_id") or "").strip()
    if not session_id or not agent_id:
        return jsonify({"error": "session_id and agent_participant_id required"}), 400
    try:
        score = float(data.get("score", 0.5))
    except (TypeError, ValueError):
        score = 0.5
    granted, reason, extra = floor.request_floor(session_id, agent_id, score)
    out = {"granted": granted, "reason": reason, **extra}
    return jsonify(out)


@meeting_floor_bp.route("/api/meeting/floor/release", methods=["POST"])
def meeting_floor_release():
    """Body: { session_id, agent_participant_id } — response.done from an agent."""
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    agent_id = (data.get("agent_participant_id") or data.get("agent_id") or "").strip()
    if not session_id or not agent_id:
        return jsonify({"error": "session_id and agent_participant_id required"}), 400
    floor.release_holder(session_id, agent_id)
    return jsonify({"ok": True, **floor.snapshot(session_id)})


@meeting_floor_bp.route("/api/meeting/floor/clear", methods=["POST"])
def meeting_floor_clear():
    """Body: { session_id } — leave meeting / teardown."""
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    floor.clear_session(session_id)
    return jsonify({"ok": True})


@meeting_floor_bp.route("/api/meeting/floor/snapshot", methods=["GET"])
def meeting_floor_snapshot():
    session_id = (request.args.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    return jsonify(floor.snapshot(session_id))
