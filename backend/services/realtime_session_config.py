"""
Build Realtime `session` JSON for POST /v1/realtime/calls (WebRTC unified interface).
Tools mirror AgentContextProtocol action types for each experiment.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from routes.participant import get_value_from_session_params
from services.realtime_prompt_fill import (
    apply_realtime_instruction_placeholders,
    meeting_voice_floor_instructions,
    orchestrated_meeting_floor_instructions,
)


def use_azure_realtime() -> bool:
    """True when Realtime traffic should use Azure (must match routes/realtime_routes)."""
    p = (os.getenv("REALTIME_PROVIDER") or "auto").strip().lower()
    if p == "azure":
        return True
    if p == "openai":
        return False
    ep = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip()
    key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
    dep = (os.getenv("AZURE_REALTIME_DEPLOYMENT") or "").strip()
    return bool(ep and key and dep)


def first_ai_participant_id(session: Optional[Dict[str, Any]]) -> Optional[str]:
    """Stable VAD leader: first AI in session.participants order (matches frontend aiParticipantsList)."""
    if not session:
        return None
    for p in session.get("participants") or []:
        if str(p.get("type") or "").lower() in ("ai", "ai_agent"):
            pid = p.get("id") or p.get("participant_id")
            if pid is not None and str(pid).strip() != "":
                return str(pid)
    return None


def realtime_orchestrated_floor_enabled(session: Optional[Dict[str, Any]]) -> bool:
    """When True, only one agent session uses input VAD; browser dispatches one voice turn per user utterance."""
    if session is None or not session_includes_meeting_room(session):
        return False
    v = (os.getenv("REALTIME_ORCHESTRATED_FLOOR") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def session_includes_meeting_room(session: Dict[str, Any]) -> bool:
    media = get_value_from_session_params(session, "Session.Interaction.communicationMedia")
    if not media:
        return False
    if isinstance(media, list):
        return "meeting_room" in media
    if isinstance(media, str):
        return media.strip().lower() == "meeting_room"
    return False


def session_includes_text(session: Dict[str, Any]) -> bool:
    """True if text chat is enabled for this session (controls message tool + UI)."""
    media = get_value_from_session_params(session, "Session.Interaction.communicationMedia")
    if not media:
        return True
    if isinstance(media, list):
        return "text" in media
    if isinstance(media, str):
        return media.strip().lower() == "text"
    return True


def realtime_input_transcription_config(
    session: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Enables server-side transcription events on realtime input audio (meeting room live captions).
    Without `audio.input.transcription`, the API does not emit input_audio_transcription.* events.
    """
    if session is None or not session_includes_meeting_room(session):
        return None
    model = (os.getenv("REALTIME_INPUT_TRANSCRIPTION_MODEL") or "whisper-1").strip()
    if not model:
        return None
    return {"model": model}


def experiment_context_block(session: Dict[str, Any]) -> str:
    """Structured experiment state so the realtime model matches the running session."""
    lines: List[str] = [
        "## Experiment context (ground truth — follow this for tools and roles)",
    ]
    et = (session.get("experiment_type") or "").strip()
    if et:
        lines.append(f"- **Experiment type**: {et}")
    sid = (session.get("session_id") or session.get("id") or "").strip()
    if sid:
        lines.append(f"- **Session id**: {sid}")
    name = (session.get("session_name") or session.get("name") or "").strip()
    if name:
        lines.append(f"- **Session name**: {name}")
    try:
        ec = session.get("experiment_config")
        if isinstance(ec, dict):
            params = ec.get("params")
            if params is not None:
                blob = json.dumps(params, ensure_ascii=False, default=str)
                if len(blob) > 8000:
                    blob = blob[:8000] + "\n[... truncated ...]"
                lines.append("- **Experiment parameters (from config)**:\n```json\n" + blob + "\n```")
    except (TypeError, ValueError):
        pass
    lines.append("")
    return "\n".join(lines)


def tools_without_message_if_no_text(
    tools: List[Dict[str, Any]], session: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if session is None or session_includes_text(session):
        return tools
    return [t for t in tools if (t.get("name") or "") not in ("message", "send_chat_message")]


def load_prompt_instructions(experiment_type: str, participant_role: Optional[str] = None) -> str:
    if experiment_type == "wordguessing":
        prompt_name = "wordguessing_hinter" if participant_role == "hinter" else "wordguessing_guesser"
    else:
        prompt_name = f"{experiment_type}_agent"

    import os as _os

    current_dir = _os.path.dirname(_os.path.abspath(__file__))
    agent_dir = _os.path.join(_os.path.dirname(current_dir), "agent")
    prompt_file = _os.path.join(agent_dir, "prompts", f"{prompt_name}_prompt.txt")
    if _os.path.exists(prompt_file):
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                text = f.read()
                if len(text) > 12000:
                    return text[:12000] + "\n\n[... truncated ...]"
                return text
        except OSError:
            pass
    return f"You are an AI participant in experiment '{experiment_type}'. Use tools to act in the environment."


def _tool_message() -> Dict[str, Any]:
    return {
        "type": "function",
        "name": "message",
        "description": "Send a chat message. Use recipient 'all' for group chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["recipient", "content"],
        },
    }


def _tools_shapefactory() -> List[Dict[str, Any]]:
    return [
        _tool_message(),
        {
            "type": "function",
            "name": "propose_trade_offer",
            "description": "Propose buying or selling a shape with another participant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "offer_type": {"type": "string", "enum": ["buy", "sell"]},
                    "shape": {"type": "string"},
                    "price_per_unit": {"type": "number"},
                    "target_participant": {
                        "type": "string",
                        "description": "Other participant's display name",
                    },
                },
                "required": ["offer_type", "shape", "price_per_unit", "target_participant"],
            },
        },
        {
            "type": "function",
            "name": "trade_response",
            "description": "Accept or decline a pending trade offer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "response_type": {"type": "string", "enum": ["accept", "decline"]},
                    "transaction_id": {"type": "string"},
                },
                "required": ["response_type", "transaction_id"],
            },
        },
        {
            "type": "function",
            "name": "cancel_trade_offer",
            "description": "Cancel your pending trade offer.",
            "parameters": {
                "type": "object",
                "properties": {"transaction_id": {"type": "string"}},
                "required": ["transaction_id"],
            },
        },
        {
            "type": "function",
            "name": "produce_shape",
            "description": "Start producing a shape.",
            "parameters": {
                "type": "object",
                "properties": {"shape": {"type": "string"}},
                "required": ["shape"],
            },
        },
        {
            "type": "function",
            "name": "fulfill_order",
            "description": "Fulfill pending orders by task indices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Indices of tasks/orders to fulfill",
                    },
                },
                "required": ["order_indices"],
            },
        },
    ]


def _tools_daytrader() -> List[Dict[str, Any]]:
    return [
        _tool_message(),
        {
            "type": "function",
            "name": "make_investment",
            "description": "Make an investment (deducts from your balance).",
            "parameters": {
                "type": "object",
                "properties": {
                    "invest_price": {"type": "number", "description": "Dollar amount to invest"},
                    "invest_decision_type": {
                        "type": "string",
                        "enum": ["individual", "group"],
                    },
                },
                "required": ["invest_price", "invest_decision_type"],
            },
        },
    ]


def _tools_essayranking() -> List[Dict[str, Any]]:
    return [
        _tool_message(),
        {
            "type": "function",
            "name": "get_essay_content",
            "description": "Load essay PDF content into context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "essay_id": {"type": "string"},
                    "essay_name": {"type": "string"},
                },
                "required": [],
            },
        },
        {
            "type": "function",
            "name": "submit_ranking",
            "description": "Submit full ranking for all essays.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rankings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "essay_id": {"type": "string"},
                                "essay_name": {"type": "string"},
                                "rank": {"type": "integer"},
                            },
                        },
                    },
                },
                "required": ["rankings"],
            },
        },
    ]


def _tools_hiddenprofile() -> List[Dict[str, Any]]:
    return [
        _tool_message(),
        {
            "type": "function",
            "name": "get_candidate_names",
            "description": "List candidate names for voting.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        {
            "type": "function",
            "name": "submit_initial_vote",
            "description": "Submit initial vote for a candidate.",
            "parameters": {
                "type": "object",
                "properties": {"candidate_name": {"type": "string"}},
                "required": ["candidate_name"],
            },
        },
        {
            "type": "function",
            "name": "submit_final_vote",
            "description": "Submit final vote.",
            "parameters": {
                "type": "object",
                "properties": {"candidate_name": {"type": "string"}},
                "required": ["candidate_name"],
            },
        },
    ]


def _tools_maptask() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "send_map_guidance",
            "description": "Send one route-guidance message from guide to follower using the guide's map context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Follower display name (optional)"},
                    "content": {"type": "string", "description": "Guidance message for follower"},
                },
                "required": ["content"],
            },
        }
    ]


def tools_for_experiment(
    experiment_type: str, session: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    et = (experiment_type or "").lower()
    if et == "shapefactory":
        raw = _tools_shapefactory()
    elif et == "daytrader":
        raw = _tools_daytrader()
    elif et == "essayranking":
        raw = _tools_essayranking()
    elif et == "hiddenprofile":
        raw = _tools_hiddenprofile()
    elif et == "maptask":
        raw = _tools_maptask()
    else:
        raw = [_tool_message()]
    return tools_without_message_if_no_text(raw, session)


def realtime_model_id() -> str:
    """Explicit override, else Azure deployment name, else OpenAI model id."""
    override = (os.getenv("REALTIME_SESSION_MODEL") or "").strip()
    if override:
        return override
    dep = (os.getenv("AZURE_REALTIME_DEPLOYMENT") or "").strip()
    if dep:
        return dep
    return (os.getenv("OPENAI_REALTIME_MODEL") or "gpt-4o-realtime-preview-2024-12-17").strip()


def build_azure_client_secrets_session_json(
    experiment_type: str,
    participant_role: Optional[str],
    session: Optional[Dict[str, Any]] = None,
    participant: Optional[Dict[str, Any]] = None,
    *,
    is_vad_leader: bool = True,
) -> Dict[str, Any]:
    """
    Minimal `session` for Azure POST /openai/v1/realtime/client_secrets.

    Azure often returns 500 for large payloads (long instructions + many tools). We mint the
    ephemeral key with a small body, then the browser sends `session.update` with full tools
    and instructions (see `build_realtime_session_update_json`).
    """
    voice = (os.getenv("AZURE_REALTIME_VOICE") or "alloy").strip()
    if (os.getenv("AZURE_REALTIME_CLIENT_SECRETS_FULL_PROMPT") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        max_chars = int((os.getenv("AZURE_REALTIME_CLIENT_SECRETS_MAX_INSTRUCTIONS") or "8000").strip())
        meeting = "\n\n## Voice (WebRTC)\n- Session starting.\n"
        ctx = experiment_context_block(session) if session else ""
        instr = load_prompt_instructions(experiment_type, participant_role)
        if participant and session:
            instr = apply_realtime_instruction_placeholders(
                instr, experiment_type, participant, session
            )
            meeting = meeting + meeting_voice_floor_instructions(session, participant)
            if realtime_orchestrated_floor_enabled(session):
                meeting = meeting + orchestrated_meeting_floor_instructions()
        instructions = (ctx + instr + meeting)[:max_chars]
    else:
        ctx_hint = experiment_context_block(session) if session else ""
        stub_tail = (
            "Reply briefly in voice until then if the user speaks."
            if not (session and realtime_orchestrated_floor_enabled(session))
            else "Stay silent until the session update; the app will open turns for voice."
        )
        instructions = (
            (ctx_hint[:2000] + "\n" if ctx_hint else "")
            + "You are an AI participant in a collaborative experiment. "
            "Full task instructions and tools arrive in a session update immediately after connect. "
            + stub_tail
        )
    out: Dict[str, Any] = {
        "type": "realtime",
        "model": realtime_model_id(),
        "instructions": instructions,
        "audio": {"output": {"voice": voice}},
    }
    if (os.getenv("AZURE_REALTIME_CLIENT_SECRETS_FULL_AUDIO") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        turn_detection: Optional[Dict[str, Any]] = {"type": "server_vad"}
        if (
            session
            and participant
            and realtime_orchestrated_floor_enabled(session)
            and not is_vad_leader
        ):
            turn_detection = None
        audio_in: Dict[str, Any] = {
            "format": {"type": "audio/pcm", "rate": 24000},
            "turn_detection": turn_detection,
        }
        tc = realtime_input_transcription_config(session)
        if tc:
            audio_in["transcription"] = tc
        out["audio"] = {
            "input": audio_in,
            "output": {
                "format": {"type": "audio/pcm"},
                "voice": voice,
            },
        }
    return out


def build_realtime_session_update_json(
    experiment_type: str,
    participant_role: Optional[str],
    session: Optional[Dict[str, Any]] = None,
    participant: Optional[Dict[str, Any]] = None,
    *,
    is_vad_leader: bool = True,
) -> Dict[str, Any]:
    """Inner `session` object for a client `session.update` after WebRTC connects (Azure two-step)."""
    full = build_realtime_session_json(
        experiment_type,
        participant_role,
        session=session,
        participant=participant,
        is_vad_leader=is_vad_leader,
    )
    out: Dict[str, Any] = {
        "instructions": full["instructions"],
        "tools": full["tools"],
        "tool_choice": full.get("tool_choice", "auto"),
    }
    audio = full.get("audio")
    if isinstance(audio, dict):
        out["audio"] = {}
        if isinstance(audio.get("input"), dict):
            out["audio"]["input"] = {**audio["input"]}
        if isinstance(audio.get("output"), dict):
            out["audio"]["output"] = {**audio["output"]}
    return out


def build_realtime_session_json(
    experiment_type: str,
    participant_role: Optional[str],
    voice: Optional[str] = None,
    session: Optional[Dict[str, Any]] = None,
    participant: Optional[Dict[str, Any]] = None,
    *,
    is_vad_leader: bool = True,
) -> Dict[str, Any]:
    """Payload for the `session` multipart field of /v1/realtime/calls."""
    azure = use_azure_realtime()
    if azure:
        voice = voice or (os.getenv("AZURE_REALTIME_VOICE") or "alloy").strip()
    else:
        voice = voice or (os.getenv("OPENAI_REALTIME_VOICE") or "marin").strip()
    orchestrated = (
        session is not None
        and participant is not None
        and session_includes_meeting_room(session)
        and realtime_orchestrated_floor_enabled(session)
    )
    turn_detection: Optional[Dict[str, Any]]
    if orchestrated and not is_vad_leader:
        turn_detection = None
    elif azure:
        turn_detection = {"type": "server_vad"}
        if (os.getenv("AZURE_REALTIME_SEMANTIC_VAD") or "").strip().lower() in ("1", "true", "yes"):
            turn_detection = {"type": "semantic_vad", "eagerness": "auto"}
    elif orchestrated and is_vad_leader:
        # Faster end-of-speech than semantic_vad so the client can dispatch soon after the user pauses.
        turn_detection = {"type": "server_vad"}
    else:
        turn_detection = {"type": "semantic_vad"}
    ctx = experiment_context_block(session) if session else ""
    instr = load_prompt_instructions(experiment_type, participant_role)
    if participant is not None and session is not None:
        instr = apply_realtime_instruction_placeholders(
            instr, experiment_type, participant, session
        )
    meeting = (
        "\n\n## Voice (WebRTC)\n"
        "- The user speaks to you over a realtime audio connection.\n"
        "- Use tools to change the experiment state; do not claim you acted without calling the tool.\n"
        "- Confirm briefly in speech when a tool succeeds or fails.\n"
        "## Turn-taking (multi-participant meeting)\n"
        "- You may not hear other AI participants; only the human shares the same audio channel with you.\n"
        "- Do not talk over the human. Wait for a clear pause after they finish before you speak.\n"
        "- Keep replies concise so others can speak; avoid overlapping with other voices you might hear from the app.\n"
    )
    if session is not None and participant is not None:
        meeting += meeting_voice_floor_instructions(session, participant)
        if orchestrated:
            meeting += orchestrated_meeting_floor_instructions()
    tools = list(tools_for_experiment(experiment_type, session))
    tool_choice: str = "auto" if tools else "none"
    audio_input: Dict[str, Any] = {
        "format": {"type": "audio/pcm", "rate": 24000},
        "turn_detection": turn_detection,
    }
    tc = realtime_input_transcription_config(session)
    if tc:
        audio_input["transcription"] = tc
    return {
        "type": "realtime",
        "model": realtime_model_id(),
        "instructions": ctx + instr + meeting,
        "tools": tools,
        "tool_choice": tool_choice,
        "audio": {
            "input": audio_input,
            "output": {
                "format": {"type": "audio/pcm"},
                "voice": voice,
            },
        },
    }


def function_call_to_action(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Map OpenAI function name + args to AgentContextProtocol action dict."""
    if name in ("message", "send_chat_message"):
        return {
            "type": "message",
            "recipient": arguments.get("recipient") or "all",
            "content": (arguments.get("content") or "").strip(),
        }
    return {"type": name, **arguments}
