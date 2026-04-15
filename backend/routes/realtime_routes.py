"""
WebRTC Realtime API proxy: POST /v1/realtime/calls (SDP exchange) and tool execution for the browser data channel.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse

import requests
from flask import Blueprint, jsonify, request

from agent.agent_context_protocol import AgentContextProtocol
from routes.participant import find_session_by_identifier
from services.realtime_session_config import (
    build_azure_client_secrets_session_json,
    build_realtime_session_json,
    build_realtime_session_update_json,
    first_ai_participant_id,
    function_call_to_action,
    realtime_orchestrated_floor_enabled,
    session_includes_meeting_room,
    use_azure_realtime,
)

realtime_bp = Blueprint("realtime", __name__)


def _is_vad_leader_agent(sess: Dict[str, Any], agent_participant_id: str) -> bool:
    first = first_ai_participant_id(sess)
    if first is None:
        return True
    return str(first) == str(agent_participant_id)


def _parse_azure_host(endpoint: str) -> str:
    ep = (endpoint or "").strip()
    if not ep:
        return ""
    if "://" not in ep:
        ep = "https://" + ep
    return urlparse(ep).netloc or ""


def _realtime_calls_url_openai() -> str:
    return "https://api.openai.com/v1/realtime/calls"


def _azure_openai_host() -> str:
    return _parse_azure_host(os.getenv("AZURE_OPENAI_ENDPOINT", ""))


def _azure_realtime_client_secrets_url() -> str:
    """GA WebRTC: mint ephemeral token. Some Cognitive Services hosts need ?api-version=..."""
    host = _azure_openai_host()
    base = f"https://{host}/openai/v1/realtime/client_secrets"
    ver = (os.getenv("AZURE_REALTIME_CLIENT_SECRETS_API_VERSION") or "").strip()
    if ver:
        return f"{base}?api-version={quote(ver)}"
    return base


def _azure_realtime_calls_url() -> str:
    """GA WebRTC SDP exchange: Bearer ephemeral token; webrtcfilter recommended for browser."""
    host = _azure_openai_host()
    q = (os.getenv("AZURE_REALTIME_CALLS_QUERY") or "webrtcfilter=on").strip()
    if q:
        return f"https://{host}/openai/v1/realtime/calls?{q}"
    return f"https://{host}/openai/v1/realtime/calls"


def _mint_azure_ephemeral_token(session_inner: Dict[str, Any]) -> str:
    key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
    if not key:
        raise ValueError("AZURE_OPENAI_API_KEY not set")
    url = _azure_realtime_client_secrets_url()
    body = {"session": session_inner}
    headers = {"api-key": key, "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=body, timeout=60)
    if r.status_code >= 400:
        raise ValueError(
            f"[client_secrets {r.status_code}] {r.text or r.reason}"
        )
    data = r.json()
    token = (data.get("value") or "").strip()
    if not token:
        raise ValueError("client_secrets response missing value (ephemeral token)")
    return token


def _azure_realtime_sdp_exchange(ephemeral_token: str, sdp_body: str) -> tuple[str, int]:
    url = _azure_realtime_calls_url()
    headers = {
        "Authorization": f"Bearer {ephemeral_token}",
        "Content-Type": "application/sdp",
    }
    r = requests.post(url, headers=headers, data=sdp_body.encode("utf-8"), timeout=60)
    if r.status_code >= 400:
        raise ValueError(f"[realtime/calls {r.status_code}] {r.text or r.reason}")
    return r.text, r.status_code


@realtime_bp.route("/api/realtime/calls", methods=["POST"])
def realtime_calls():
    """
    WebRTC unified interface: browser sends SDP offer body; we forward to OpenAI or Azure with session JSON.
    Query: session_id, agent_participant_id (AI participant whose tools we run).
    """
    session_id = request.args.get("session_id") or ""
    agent_participant_id = request.args.get("agent_participant_id") or ""
    if not session_id or not agent_participant_id:
        return jsonify({"error": "session_id and agent_participant_id query params required"}), 400

    session_key, sess = find_session_by_identifier(session_id)
    if not sess:
        return jsonify({"error": "Session not found"}), 404

    if not session_includes_meeting_room(sess):
        return jsonify({"error": "Session does not have meeting_room communication enabled"}), 400

    participants = sess.get("participants", [])
    agent_p = None
    for p in participants:
        if p.get("id") == agent_participant_id:
            agent_p = p
            break
    if not agent_p:
        return jsonify({"error": "agent_participant_id not in session"}), 404
    if (agent_p.get("type") or "").lower() not in ("ai", "ai_agent"):
        return jsonify({"error": "agent_participant_id must be an AI participant"}), 400

    experiment_type = sess.get("experiment_type") or ""
    role = agent_p.get("role")
    is_vad_leader = _is_vad_leader_agent(sess, agent_participant_id)
    session_payload = build_realtime_session_json(
        experiment_type,
        role,
        session=sess,
        participant=agent_p,
        is_vad_leader=is_vad_leader,
    )

    sdp_body = request.get_data(as_text=True)
    if not sdp_body or not sdp_body.strip():
        return jsonify({"error": "Expected raw SDP body"}), 400

    session_json_str = json.dumps(session_payload)

    files = {
        "sdp": ("offer.sdp", sdp_body.encode("utf-8"), "application/sdp"),
        "session": (None, session_json_str, "application/json"),
    }

    try:
        if use_azure_realtime():
            # Azure GA WebRTC: api-key only for /client_secrets; /realtime/calls needs Bearer ephemeral token.
            try:
                ephemeral = _mint_azure_ephemeral_token(
                    build_azure_client_secrets_session_json(
                        experiment_type,
                        role,
                        session=sess,
                        participant=agent_p,
                        is_vad_leader=is_vad_leader,
                    )
                )
                answer_sdp, _status = _azure_realtime_sdp_exchange(ephemeral, sdp_body)
            except ValueError as e:
                return jsonify({"error": str(e)}), 502
            return answer_sdp, 200, {"Content-Type": "application/sdp"}
        else:
            key = (os.getenv("OPENAI_API_KEY") or "").strip()
            if not key:
                return jsonify({"error": "OPENAI_API_KEY not set"}), 503
            headers = {"Authorization": f"Bearer {key}", "OpenAI-Beta": "realtime=v1"}
            r = requests.post(_realtime_calls_url_openai(), headers=headers, files=files, timeout=60)

        if r.status_code >= 400:
            return (
                jsonify({"error": r.text or "realtime/calls failed", "status": r.status_code}),
                r.status_code,
            )
        return r.text, 200, {"Content-Type": "application/sdp"}
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


@realtime_bp.route("/api/realtime/session_update", methods=["GET"])
def realtime_session_update():
    """
    After WebRTC connects, the client sends this on the `oai-events` channel as `session.update`.
    Ensures full instructions + tools (esp. experiment context) apply for Azure and OpenAI.
    """
    session_id = request.args.get("session_id") or ""
    agent_participant_id = request.args.get("agent_participant_id") or ""
    if not session_id or not agent_participant_id:
        return jsonify({"error": "session_id and agent_participant_id required"}), 400

    _sk, sess = find_session_by_identifier(session_id)
    if not sess:
        return jsonify({"error": "Session not found"}), 404
    if not session_includes_meeting_room(sess):
        return jsonify({"error": "Session does not have meeting_room communication enabled"}), 400

    participants = sess.get("participants", [])
    agent_p = None
    for p in participants:
        if p.get("id") == agent_participant_id:
            agent_p = p
            break
    if not agent_p:
        return jsonify({"error": "agent_participant_id not in session"}), 404
    if (agent_p.get("type") or "").lower() not in ("ai", "ai_agent"):
        return jsonify({"error": "agent_participant_id must be an AI participant"}), 400

    experiment_type = sess.get("experiment_type") or ""
    role = agent_p.get("role")
    is_vad_leader = _is_vad_leader_agent(sess, agent_participant_id)
    inner = build_realtime_session_update_json(
        experiment_type,
        role,
        session=sess,
        participant=agent_p,
        is_vad_leader=is_vad_leader,
    )
    return jsonify(
        {
            "events": [{"type": "session.update", "session": inner}],
            "orchestrated_floor": realtime_orchestrated_floor_enabled(sess),
            "is_vad_leader": is_vad_leader,
        }
    )


@realtime_bp.route("/api/realtime/execute_function", methods=["POST"])
def execute_function():
    """Execute a Realtime function call via AgentContextProtocol (browser sends after response.done)."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    agent_participant_id = data.get("agent_participant_id")
    name = data.get("name")
    arguments = data.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    if not session_id or not agent_participant_id or not name:
        return jsonify({"error": "session_id, agent_participant_id, name required"}), 400
    if not isinstance(arguments, dict):
        arguments = {}

    session_key, sess = find_session_by_identifier(session_id)
    if not sess:
        return jsonify({"error": "Session not found"}), 404

    participants = sess.get("participants", [])
    agent_p = None
    for p in participants:
        if p.get("id") == agent_participant_id:
            agent_p = p
            break
    if not agent_p:
        return jsonify({"error": "Agent not in session"}), 404
    if (agent_p.get("type") or "").lower() not in ("ai", "ai_agent"):
        return jsonify({"error": "Not an AI participant"}), 400

    experiment_type = sess.get("experiment_type") or ""
    if name in ("request_turn", "bid_speak"):
        out = json.dumps({"success": True, "turn_request_recorded": True}, default=str)
        return jsonify({"output": out})

    protocol = AgentContextProtocol(agent_participant_id, session_id, experiment_type)
    action = function_call_to_action(name, arguments)
    try:
        result = protocol._execute_single_action(action, agent_p, sess, session_key)
        out = json.dumps(result, default=str)
        return jsonify({"output": out})
    except Exception as e:
        return jsonify({"output": json.dumps({"success": False, "error": str(e)})})

