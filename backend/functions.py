"""
Experiment-specific special initialization functions.

These functions are referenced by participant config via init_path like:
  "Functions.assign_tasks"
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename


def parse_iso_timestamp_utc(s: str) -> datetime:
    """
    Parse completion/start timestamps for shape production.
    Strings ending in Z are UTC. Naive ISO strings (legacy) are interpreted as UTC so
    they match Docker servers and align with browser Date parsing when Z is used.
    """
    if not isinstance(s, str) or not s.strip():
        raise ValueError("empty timestamp")
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_session_param_value(session: dict, path: str) -> Any:
    """
    Minimal resolver for Session.Params.* paths.
    Supports:
    - Flat dict on session['params'] (researcher live-save from setup.vue)
    - Nested list schema: [{'Cluster': [{path, value?, default}, ...]}, ...]
    """
    if not session or not isinstance(session, dict):
        return None
    if not path or not isinstance(path, str):
        return None

    parts = path.split(".")
    if len(parts) < 3 or parts[0] != "Session" or parts[1] != "Params":
        return None

    param_name = parts[2]
    params = session.get("params")

    # Researcher UI stores params as a flat dict keyed by camelCase param name
    if isinstance(params, dict) and param_name in params:
        return params[param_name]

    # Nested list: template or legacy session.params
    if not isinstance(params, list):
        exp_cfg = session.get("experiment_config")
        if isinstance(exp_cfg, dict) and isinstance(exp_cfg.get("params"), list):
            params = exp_cfg["params"]

    if not isinstance(params, list):
        return None

    for cluster in params:
        if not isinstance(cluster, dict):
            continue
        for _cluster_name, items in cluster.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and item.get("path") == path:
                    return item.get("value", item.get("default"))

    return None


def assign_tasks(participant: dict, session: dict, param_cfg: Optional[dict] = None) -> list:
    """
    ShapeFactory: initialize tasks by sampling (with replacement) from the available shapes.
    - Available shape types count is controlled by Session.Params.shapesTypes
    - Task list length is controlled by Session.Params.shapesOrder

    Notes:
    - `param_cfg['options']` is treated as the global shape pool; it can be longer than shapesTypes.
    - Sampling is with replacement (tasks can repeat).
    """
    shapes_types = _get_session_param_value(session, "Session.Params.shapesTypes")
    shapes_order = _get_session_param_value(session, "Session.Params.shapesOrder")

    try:
        shapes_types = int(shapes_types) if shapes_types is not None else None
    except Exception:
        shapes_types = None

    try:
        shapes_order = int(shapes_order) if shapes_order is not None else None
    except Exception:
        shapes_order = None

    shapes_order = shapes_order if isinstance(shapes_order, int) and shapes_order > 0 else 0

    options = (param_cfg or {}).get("options", [])
    available = options if isinstance(options, list) else []

    if isinstance(shapes_types, int) and shapes_types > 0:
        available = available[:shapes_types]

    if not available or shapes_order <= 0:
        return []

    return [random.choice(available) for _ in range(shapes_order)]


def assign_map_for_maptask(participant: dict, session: dict, param_cfg: Optional[dict] = None) -> Optional[dict]:
    """
    Map Task: assign the appropriate map to the participant based on their role.
    - Guide gets a map with role='guide'
    - Follower gets a map with role='follower'

    Session maps may live in a flat params dict (after upload) or only in nested experiment
    params — use the same resolver as the rest of the backend.
    """
    role_raw = participant.get('role') or participant.get('experiment_params', {}).get('role')
    role = (str(role_raw).strip().lower() if role_raw else '')
    if not role:
        return None

    # Lazy import avoids circular import with routes.participant
    from routes.participant import get_value_from_session_params

    maps = get_value_from_session_params(session, 'Session.Params.maps')
    if not isinstance(maps, list) or len(maps) == 0:
        return None

    def _norm_map_role(mr: Any) -> str:
        return (str(mr or 'guide').strip().lower())

    for m in maps:
        if not isinstance(m, dict):
            continue
        if _norm_map_role(m.get('role')) == role:
            out = dict(m)
            fn = out.get('filename')
            if fn and not out.get('file_path'):
                safe = secure_filename(str(fn))
                if safe:
                    out['file_path'] = f'/api/maps/{safe}'
            return out
    return None


def start_production(participant: dict, session: dict, shape: str) -> Dict[str, Any]:
    """
    Start production of a shape for a participant.
    
    This function:
    1. Validates that the participant has enough money
    2. Checks if production limit is not exceeded
    3. Deducts money based on specialty vs regular cost
    4. Adds shape to in_production with completion time
    5. Updates production_number
    
    Args:
        participant: Participant dict
        session: Session dict
        shape: Shape name to produce (e.g., "circle", "square")
    
    Returns:
        Dict with 'success' (bool) and 'message' (str) or 'error' (str)
    """
    if not shape or not isinstance(shape, str):
        return {'success': False, 'error': 'Invalid shape'}
    
    # Get session parameters
    regular_cost = _get_session_param_value(session, "Session.Params.regularCost")
    specialty_cost = _get_session_param_value(session, "Session.Params.specialtyCost")
    production_time = _get_session_param_value(session, "Session.Params.productionTime")
    max_production_num = _get_session_param_value(session, "Session.Params.maxProductionNum")
    
    # Default values if not configured
    regular_cost = int(regular_cost) if regular_cost is not None else 40
    specialty_cost = int(specialty_cost) if specialty_cost is not None else 15
    production_time = int(production_time) if production_time is not None else 30
    max_production_num = int(max_production_num) if max_production_num is not None else 3
    
    # Get participant data
    exp_params = participant.get('experiment_params', {})
    money = exp_params.get('money', 0)
    specialty = participant.get('specialty', '')
    production_number = exp_params.get('production_number', 0)
    in_production = exp_params.get('in_production', [])
    
    # Ensure in_production is a list
    if not isinstance(in_production, list):
        in_production = []
    
    # Check if production limit is reached
    # Total production = completed (production_number) + in progress (len(in_production))
    total_production = production_number + len(in_production)
    if total_production >= max_production_num:
        return {'success': False, 'error': f'Production limit reached ({max_production_num}). Completed: {production_number}, In progress: {len(in_production)}'}
    
    # Determine cost based on specialty
    is_specialty = (shape.lower() == specialty.lower())
    cost = specialty_cost if is_specialty else regular_cost
    
    # Check if participant has enough money
    if money < cost:
        return {'success': False, 'error': f'Insufficient funds. Need ${cost}, have ${money}'}
    
    # Completion instants in UTC with Z suffix so browsers parse as UTC, not local wall time
    now = datetime.now(timezone.utc)
    completion_time = now + timedelta(seconds=production_time)
    completion_timestamp = completion_time.isoformat().replace("+00:00", "Z")
    started_timestamp = now.isoformat().replace("+00:00", "Z")

    # Create production entry
    production_entry = {
        'shape': shape,
        'started_at': started_timestamp,
        'completion_time': completion_timestamp,
        'production_time_seconds': production_time
    }
    
    # Update participant
    exp_params['money'] = money - cost
    # Note: production_number is incremented when production completes, not when it starts
    
    # Add to in_production list
    in_production.append(production_entry)
    exp_params['in_production'] = in_production
    
    participant['experiment_params'] = exp_params
    
    return {
        'success': True,
        'message': f'Production started for {shape}',
        'cost': cost,
        'remaining_money': exp_params['money'],
        'production_number': production_number,  # Current completed count
        'in_production_count': len(in_production),  # Current in-progress count
        'completion_time': completion_timestamp
    }


FUNCTIONS_REGISTRY: Dict[str, Callable[[dict, dict, Optional[dict]], Any]] = {
    "assign_tasks": assign_tasks,
    "assign_map_for_maptask": assign_map_for_maptask,
    "start_production": start_production,
}


def resolve_function(init_path: str) -> Optional[Callable[[dict, dict, Optional[dict]], Any]]:
    """
    Resolve init_path like "Functions.assign_tasks" into a callable.
    """
    if not isinstance(init_path, str) or not init_path.startswith("Functions."):
        return None
    func_name = init_path.split(".", 1)[1].strip()
    return FUNCTIONS_REGISTRY.get(func_name)


