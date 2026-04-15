"""
Apply the same instruction placeholders as AgentRunner._build_prompt (without live perception),
so WebRTC Realtime sessions receive specialty, money, orders, etc.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from routes.participant import get_value_from_session_params


def _build_participants_list_str(experiment_type: str, session: Dict[str, Any]) -> str:
    lines: list[str] = []
    for p in session.get("participants") or []:
        p_name = p.get("name") or p.get("participant_name") or p.get("id") or "?"
        et = (experiment_type or "").lower()
        if et == "shapefactory":
            p_specialty = p.get("specialty", "")
            lines.append(f"- {p_name}: Specialty = {p_specialty}")
        elif et == "wordguessing":
            p_role = p.get("role", "")
            lines.append(f"- {p_name}: Role = {p_role}")
        elif et == "maptask":
            p_role = p.get("role", "")
            lines.append(f"- {p_name}: Role = {p_role}")
        else:
            lines.append(f"- {p_name}")
    return "\n".join(lines)


def _replace_shapefactory(
    prompt: str, participant: Dict[str, Any], session: Dict[str, Any]
) -> str:
    starting_money = get_value_from_session_params(session, "Session.Params.startingMoney") or 200
    specialty_cost = get_value_from_session_params(session, "Session.Params.specialtyCost") or 15
    regular_cost = get_value_from_session_params(session, "Session.Params.regularCost") or 40
    production_time = get_value_from_session_params(session, "Session.Params.productionTime") or 30
    max_production_num = get_value_from_session_params(session, "Session.Params.maxProductionNum") or 3
    price_min = get_value_from_session_params(session, "Session.Params.minTradePrice") or 15
    price_max = get_value_from_session_params(session, "Session.Params.maxTradePrice") or 100
    incentive_money = get_value_from_session_params(session, "Session.Params.incentiveMoney") or 60
    shapes_order = get_value_from_session_params(session, "Session.Params.shapesOrder") or 4

    specialty = participant.get("specialty", "")
    exp_params = participant.get("experiment_params", {}) or {}
    tasks = exp_params.get("tasks", [])

    prompt = prompt.replace("{shape_amount_per_order}", str(shapes_order))
    prompt = prompt.replace("{incentive_money}", str(incentive_money))
    prompt = prompt.replace("{starting_money}", str(starting_money))
    prompt = prompt.replace("{specialty_shape}", specialty)
    prompt = prompt.replace("{specialty_cost}", str(specialty_cost))
    prompt = prompt.replace("{regular_cost}", str(regular_cost))
    prompt = prompt.replace("{production_time}", str(production_time))
    prompt = prompt.replace("{max_production_num}", str(max_production_num))
    prompt = prompt.replace("{price_min}", str(price_min))
    prompt = prompt.replace("{price_max}", str(price_max))
    prompt = prompt.replace("{current_orders}", str(tasks))
    return prompt


def _replace_daytrader(
    prompt: str, participant: Dict[str, Any], session: Dict[str, Any]
) -> str:
    starting_money = get_value_from_session_params(session, "Session.Params.startingMoney") or 200
    min_trade_price = get_value_from_session_params(session, "Session.Params.minTradePrice") or 15
    max_trade_price = get_value_from_session_params(session, "Session.Params.maxTradePrice") or 100

    exp_params = participant.get("experiment_params", {}) or {}
    investment_history_list = exp_params.get("investment_history", [])
    investment_history = json.dumps(investment_history_list) if investment_history_list else "[]"

    prompt = prompt.replace("{starting_money}", str(starting_money))
    prompt = prompt.replace("{min_trade_price}", str(min_trade_price))
    prompt = prompt.replace("{max_trade_price}", str(max_trade_price))
    prompt = prompt.replace("{investment_history}", investment_history)
    return prompt


def _replace_essayranking(
    prompt: str, participant: Dict[str, Any], session: Dict[str, Any]
) -> str:
    assigned_essays = session.get("essays", []) or participant.get("experiment_params", {}).get(
        "essays", []
    )
    essay_names: list[str] = []
    if assigned_essays:
        for essay in assigned_essays:
            if isinstance(essay, dict):
                essay_name = (
                    essay.get("title")
                    or essay.get("original_filename")
                    or essay.get("filename", "").replace(".pdf", "")
                )
                if essay_name:
                    essay_names.append(essay_name)
            elif isinstance(essay, str):
                essay_names.append(essay)
    assigned_essays_str = ", ".join(essay_names) if essay_names else "No essays assigned"
    prompt = prompt.replace("{assigned_essays}", assigned_essays_str)
    return prompt


def _replace_wordguessing(
    prompt: str, participant: Dict[str, Any], session: Dict[str, Any]
) -> str:
    role = participant.get("role", "")
    all_participants = session.get("participants", [])

    if role == "guesser":
        hinter = next((p for p in all_participants if p.get("role") == "hinter"), None)
        hinter_name = (hinter.get("name") or hinter.get("participant_name")) if hinter else "Unknown"
        prompt = prompt.replace("{hinter_participant}", hinter_name)
    elif role == "hinter":
        guesser = next((p for p in all_participants if p.get("role") == "guesser"), None)
        guesser_name = (guesser.get("name") or guesser.get("participant_name")) if guesser else "Unknown"
        prompt = prompt.replace("{guesser_participant}", guesser_name)
        exp_params = participant.get("experiment_params", {}) or {}
        assigned_words = exp_params.get("assigned_words", [])
        assigned_words_str = ", ".join(assigned_words) if assigned_words else "None"
        prompt = prompt.replace("{assigned_words}", assigned_words_str)
    return prompt


def _replace_hiddenprofile(
    prompt: str, participant: Dict[str, Any], session: Dict[str, Any]
) -> str:
    exp_params = participant.get("experiment_params", {}) or {}
    assigned_doc = exp_params.get("candidate_document")
    if isinstance(assigned_doc, dict):
        assigned_doc_str = (
            assigned_doc.get("title")
            or assigned_doc.get("original_filename")
            or str(assigned_doc.get("filename", ""))
            or "Document assigned (content not inlined in voice session)"
        )
    elif isinstance(assigned_doc, str) and assigned_doc.strip():
        assigned_doc_str = assigned_doc
    else:
        assigned_doc_str = "No document assigned"

    candidate_names = get_value_from_session_params(session, "Session.Params.candidateNames")
    if candidate_names:
        if isinstance(candidate_names, list):
            candidate_list_str = ", ".join(str(x) for x in candidate_names)
        elif isinstance(candidate_names, str):
            if "," in candidate_names:
                names = [name.strip() for name in candidate_names.split(",") if name.strip()]
                candidate_list_str = ", ".join(names)
            else:
                candidate_list_str = candidate_names.strip()
        else:
            candidate_list_str = str(candidate_names)
    else:
        candidate_list_str = "No candidates available"

    prompt = prompt.replace("{assigned_doc}", assigned_doc_str)
    prompt = prompt.replace("{candidate_list}", candidate_list_str)
    return prompt


def _replace_maptask(
    prompt: str, participant: Dict[str, Any], session: Dict[str, Any]
) -> str:
    role = participant.get("role") or "guide"
    exp_params = participant.get("experiment_params", {}) or {}
    assigned_map = exp_params.get("map")
    if isinstance(assigned_map, dict):
        map_display = (
            assigned_map.get("file_path")
            or assigned_map.get("original_filename")
            or assigned_map.get("filename")
            or str(assigned_map)
        )
    elif assigned_map:
        map_display = str(assigned_map)
    else:
        map_display = "No map assigned"

    prompt = prompt.replace("{participant_role}", str(role))
    prompt = prompt.replace("{assigned_map}", map_display)
    return prompt


def orchestrated_meeting_floor_instructions() -> str:
    """Browser picks one speaker per user utterance; others get a system context line."""
    return (
        "\n## Orchestrated voice floor (mandatory)\n"
        "- The **application** decides when you may **speak aloud** after the user talks. "
        "Do **not** start a spoken reply on your own right after every user utterance.\n"
        "- When it is your turn to speak, the app will trigger a normal voice response for you. "
        "Until then, stay silent even if you hear the user pause.\n"
        "- If another agent was chosen to speak, you will receive a **system** message such as "
        "\"[name] is speaking. Content: …\" — treat that as context only; **do not** speak during that round.\n"
    )


def meeting_voice_floor_instructions(session: Dict[str, Any], participant: Dict[str, Any]) -> str:
    """
    Tell each Realtime agent their name vs others, and to stay silent when the user addresses someone else.
    Pairs with client-side response.cancel so only one agent speaks at a time when possible.
    """
    my_id = str(participant.get("id") or participant.get("participant_id") or "")
    my_name = (participant.get("name") or participant.get("participant_name") or "").strip()
    label = my_name or my_id or "you"
    all_names: list[str] = []
    for p in session.get("participants") or []:
        nm = (p.get("name") or p.get("participant_name") or p.get("id") or "").strip()
        if nm:
            all_names.append(nm)
    roster = ", ".join(all_names) if all_names else "(unknown participants)"
    return (
        "\n## Addressing and floor (critical)\n"
        f"- **You are {label}** (participant id: {my_id or 'n/a'}).\n"
        f"- **Everyone in this session**: {roster}.\n"
        "- If the user clearly speaks to **one** other person by name or direct address "
        '(e.g. "Jamie, …", "Hey Sam …") and that person is **not** you, **stay completely silent** '
        "(do not produce spoken audio). You may still use tools if the task requires it.\n"
        "- If the user addresses **you** by name, or **everyone / all / the group**, or it is unclear who they mean, "
        "you may answer briefly in voice.\n"
        "- Prefer short utterances; the app may stop overlapping voices — do not compete to speak.\n"
    )


def apply_realtime_instruction_placeholders(
    prompt: str,
    experiment_type: str,
    participant: Dict[str, Any],
    session: Dict[str, Any],
) -> str:
    """Match AgentRunner common + experiment-specific placeholder substitution (no perception block)."""
    communication_level = (
        get_value_from_session_params(session, "Session.Interaction.communicationLevel")
        or "Private Messaging"
    )
    participant_name = participant.get("name") or participant.get("participant_name") or ""
    mbti = participant.get("mbti", "unknown")
    participants_list_str = _build_participants_list_str(experiment_type, session)

    out = prompt
    out = out.replace("{participant_code}", str(participant_name))
    out = out.replace("{personality_name}", str(mbti))
    out = out.replace("{mbti_type}", str(mbti))
    out = out.replace("{personality_description}", f"You have {mbti} personality traits.")
    out = out.replace("{participants_list}", participants_list_str)
    out = out.replace("{communication_level}", str(communication_level))

    et = (experiment_type or "").lower()
    if et == "shapefactory":
        out = _replace_shapefactory(out, participant, session)
    elif et == "daytrader":
        out = _replace_daytrader(out, participant, session)
    elif et == "essayranking":
        out = _replace_essayranking(out, participant, session)
    elif et == "wordguessing":
        out = _replace_wordguessing(out, participant, session)
    elif et == "hiddenprofile":
        out = _replace_hiddenprofile(out, participant, session)
    elif et == "maptask":
        out = _replace_maptask(out, participant, session)

    return out
