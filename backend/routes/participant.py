# REST API for participants

from flask import request, jsonify, Blueprint, send_from_directory
import routes.session as session_module  # Import session module to access sessions storage
import os
import tempfile
import uuid
from config.experiments import PARTICIPANTS, get_experiment_by_id
from websocket.handlers import broadcast_participant_update
import copy
import uuid
from datetime import datetime
from functions import resolve_function, start_production

# Create a blueprint for participant routes
participant_bp = Blueprint('participant', __name__)

# Access sessions storage from session module
sessions = session_module.sessions


def _log_human_action(session_key, found_session, participant_id, action_type, action_content,
                      result='success', metadata=None, data=None, page=None, map_image=None):
    """Helper to log human participant action. data is the request JSON for screenshot/html_snapshot."""
    actual_session_id = found_session.get('session_id') or session_key
    participant = next((p for p in found_session.get('participants', []) if p.get('id') == participant_id), None)
    is_human = (participant.get('type', '') or '').lower() not in ('ai', 'ai_agent')
    if not is_human:
        return  # Only log human actions from HTTP routes (agent actions logged in agent_context_protocol)
    from services.action_logger import log_action
    d = data or {}
    log_action(
        session_id=actual_session_id,
        participant_id=participant_id,
        is_human=True,
        action_type=action_type,
        action_content=action_content,
        result=result,
        metadata=metadata or {},
        page=page or (metadata.get('page') if metadata else None),
        experiment_type=found_session.get('experiment_type', ''),
        screenshot=d.get('screenshot'),
        html_snapshot=d.get('html_snapshot'),
        map_image=map_image or d.get('map_image'),
        session=found_session,
        participant=participant,
    )

def find_session_by_identifier(session_identifier):
    """Find session by ID or name"""
    from urllib.parse import unquote
    session_identifier = unquote(session_identifier)
    
    # Try to find by session_id first (UUID format)
    if session_identifier in sessions:
        return session_identifier, sessions[session_identifier]
    
    # Try to find by session_name (case-insensitive)
    for sid, session in sessions.items():
        if session.get('session_name', '').lower() == session_identifier.lower():
            return sid, session
    
    return None, None

def find_participant_by_name(participant_name, session):
    """Find participant by name in a session (case-insensitive)"""
    if not participant_name or not session:
        return None
    
    participants_list = session.get('participants', [])
    
    # Search for participant by name (case-insensitive)
    for participant in participants_list:
        # Check both 'name' and 'participant_name' fields for compatibility
        participant_name_field = participant.get('name') or participant.get('participant_name')
        if participant_name_field and participant_name_field.lower() == participant_name.lower():
            return participant
    
    return None

def get_value_from_session_params(session, path):
    """
    Get value from session params based on path (e.g., 'Session.Params.startingMoney' or 'Session.essays').
    Returns the value if found, None otherwise.
    """
    if not path or not isinstance(path, str):
        return None
    
    # Parse path: Session.Params.startingMoney -> ['Session', 'Params', 'startingMoney']
    # or Session.essays -> ['Session', 'essays']
    parts = path.split('.')
    
    if len(parts) < 2 or parts[0] != 'Session':
        return None
    
    # Handle Session.xxx (top-level session fields like Session.essays)
    if len(parts) == 2:
        field_name = parts[1]  # e.g., 'essays'
        value = session.get(field_name) if isinstance(session, dict) else None
        # Debug logging for essays
        if field_name == 'essays':
            print(f'[get_value_from_session_params] Getting Session.essays: {len(value) if isinstance(value, list) else "not a list"} items')
            print(f'[get_value_from_session_params] Essays value: {value}')
        return value
    
    # Handle Session.Params.xxx or Session.Interaction.xxx
    if len(parts) < 3:
        return None
    
    section = parts[1]  # 'Params' or 'Interaction'
    param_name = parts[2]  # e.g., 'startingMoney'
    
    # Get the section from session
    section_data = session.get(section.lower(), None)

    # For params, first try direct access (for flattened structure like {"duration": 30})
    # This is the structure used when session.params is saved from frontend
    if section.lower() == 'params' and isinstance(section_data, dict):
        if param_name in section_data:
            value = section_data[param_name]
            print(f'[get_value_from_session_params] Found {path} in flattened params: {value}')
            return value

    # Fallback: if params section is missing or not in the expected list format,
    # try to use experiment_config.params (which always exists after experiment_type is set)
    if section.lower() == 'params':
        if not isinstance(section_data, list):
            exp_cfg = session.get('experiment_config')
            if isinstance(exp_cfg, dict) and isinstance(exp_cfg.get('params'), list):
                section_data = exp_cfg['params']

    if section_data is None:
        return None
    
    # Search for the param in the nested structure
    # session['params'] (or experiment_config['params']) is a list of dicts,
    # each dict has categories with lists of items
    if section.lower() == 'params' and isinstance(section_data, list):
        for param_group in section_data:
            if isinstance(param_group, dict):
                for category, items in param_group.items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict) and item.get('path') == path:
                                # Return the value if it exists, otherwise return default
                                return item.get('value', item.get('default'))
    
    # For interaction, it's a dict structure
    elif section.lower() == 'interaction' and isinstance(section_data, dict):
        # First, try direct access (for flattened structure like {"awarenessDashboard": {...}})
        # This is the structure used when session.interaction is saved from frontend
        if param_name in section_data:
            value = section_data[param_name]
            # Debug logging for awarenessDashboard
            if path == 'Session.Interaction.awarenessDashboard':
                print(f'[get_value_from_session_params] Found {path} via direct access: {value}')
            return value
        
        # If not found, try nested structure (for config structure with path fields)
        # This is the structure used in experiment config definitions
        def find_in_interaction(data, target_path):
            if isinstance(data, dict):
                # Check if this dict has the path we're looking for
                if 'path' in data and data['path'] == target_path:
                    # Return value if set, otherwise default
                    # For tiered_checkbox, value might be a dict with 'enabled' and 'items'
                    value = data.get('value')
                    if value is not None:
                        return value
                    # Fallback to default
                    default = data.get('default')
                    if default is not None:
                        return default
                    return None
                # Recursively search in values
                for value in data.values():
                    result = find_in_interaction(value, target_path)
                    if result is not None:
                        return result
            elif isinstance(data, list):
                for item in data:
                    result = find_in_interaction(item, target_path)
                    if result is not None:
                        return result
            return None
        
        result = find_in_interaction(section_data, path)
        
        # Debug logging for awarenessDashboard
        if path == 'Session.Interaction.awarenessDashboard':
            print(f'[get_value_from_session_params] Looking for {path}')
            print(f'[get_value_from_session_params] Param name: {param_name}')
            print(f'[get_value_from_session_params] Section data keys: {list(section_data.keys()) if isinstance(section_data, dict) else "not a dict"}')
            print(f'[get_value_from_session_params] Direct access result: {section_data.get(param_name) if isinstance(section_data, dict) else "N/A"}')
            print(f'[get_value_from_session_params] Nested search result: {result}')
            print(f'[get_value_from_session_params] Final result: {result or section_data.get(param_name) if isinstance(section_data, dict) else result}')
        
        return result
    
    return None

def get_participant_config(experiment_id, session=None):
    """
    Get participant config for a given experiment_id.
    If session is provided, dynamically update options based on session params.
    Returns a deep copy of the participant config.
    """
    # Find participant config for this experiment
    participant_config = None
    for participant_group in PARTICIPANTS:
        if experiment_id in participant_group:
            participant_config = participant_group[experiment_id]
            break
    
    if not participant_config:
        return None
    
    # Deep copy to avoid modifying the original
    config_copy = copy.deepcopy(participant_config)
    
    # If session is provided, update options based on session params
    if session and len(config_copy) > 0:
        participant_template = config_copy[0]
        if 'experiment_params' in participant_template:
            for param_name, param_config in participant_template['experiment_params'].items():
                # Check if this param has options_limit_path
                if isinstance(param_config, dict) and 'options_limit_path' in param_config:
                    limit_path = param_config['options_limit_path']
                    limit_value = get_value_from_session_params(session, limit_path)
                    
                    if limit_value is not None and isinstance(limit_value, (int, float)):
                        # Limit the options based on the limit value
                        all_options = param_config.get('options', [])
                        if isinstance(all_options, list):
                            limit_int = int(limit_value)
                            param_config['options'] = all_options[:limit_int]
    
    return config_copy

def generate_participant_interface_config(session, participant):
    """
    Based on the session configuration, generate the configuration (e.g., UI elements) for the participant.
    """
    experiment_id = session.get('experiment_type')
    if not experiment_id:
        return None
    
    # Get the participant configuration
    participant_config = get_participant_config(experiment_id, session)
    if not participant_config or len(participant_config) == 0:
        return None
    
    participant_template = participant_config[0]
    
    # Get the participant interface configuration
    participant_interface_config = participant_template.get('interface', {})
    
    # Get the participant interface configuration
    return participant_interface_config
    
    # Get the session configuration
    return None

def update_participant_experiment_params(participant, session):
    """
    Update participant object so it can be rendered by the frontend:
    1) Initialize/refresh `participant['experiment_params']` using participant config `init_path` (Session.Params.*).
    2) Build participant UI elements (`participant['interface']`) from experiment default interface, but adjusted by
       interaction controls (e.g., awareness dashboard enabled/items).
       The frontend currently only treats `visible_if` as boolean, so we evaluate/filter here.
       We also resolve each binding's `path` to concrete values (binding.value) for display.
    """
    def _get_participant_value_by_path(p, path):
        """
        Resolve 'Participant.xxx[.yyy]' against participant dict.
        We support reading from either top-level participant fields or participant['experiment_params'].
        """
        if not path or not isinstance(path, str):
            return None
        parts = path.split('.')
        if len(parts) < 2 or parts[0] != 'Participant':
            return None

        # Try top-level first, then experiment_params
        cur = p
        # Special-case common aliasing: wealth -> money
        alias_map = {'wealth': 'money'}

        for idx, key in enumerate(parts[1:]):
            # First hop: allow aliasing
            if idx == 0 and key in alias_map:
                key_candidates = [key, alias_map[key]]
            else:
                key_candidates = [key]

            next_val = None
            # On first hop only, fall back to experiment_params if missing at top-level
            if idx == 0:
                for k in key_candidates:
                    if isinstance(cur, dict) and k in cur:
                        next_val = cur.get(k)
                        break
                if next_val is None:
                    exp = (p or {}).get('experiment_params', {})
                    for k in key_candidates:
                        if isinstance(exp, dict) and k in exp:
                            next_val = exp.get(k)
                            break
            else:
                if isinstance(cur, dict):
                    for k in key_candidates:
                        if k in cur:
                            next_val = cur.get(k)
                            break

            cur = next_val
            if cur is None:
                return None
        return cur

    def _find_interaction_param(interaction_data, target_path):
        """
        Find an interaction param dict by its 'path' in the session's interaction config.
        This supports both the original experiment-config structure and updated session interaction values.
        """
        if not interaction_data or not target_path:
            return None

        def walk(node):
            if isinstance(node, dict):
                if node.get('path') == target_path:
                    return node
                for v in node.values():
                    r = walk(v)
                    if r is not None:
                        return r
            elif isinstance(node, list):
                for it in node:
                    r = walk(it)
                    if r is not None:
                        return r
            return None

        return walk(interaction_data)

    def _get_interaction_value(session_obj, base_path, sub_path_parts=None):
        """
        Get Session.Interaction.* value (and optionally drill down into returned dict via sub_path_parts).
        """
        val = get_value_from_session_params(session_obj, base_path)

        # Fallback: for interaction params, also look at session['interaction'] where we store runtime values
        if val is None and isinstance(session_obj, dict) and base_path.startswith("Session.Interaction."):
            parts = base_path.split(".")
            if len(parts) >= 3:
                param_key = parts[2]
                interaction_state = session_obj.get("interaction", {})
                if isinstance(interaction_state, dict):
                    val = interaction_state.get(param_key)

        if sub_path_parts and val is not None:
            cur = val
            for k in sub_path_parts:
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    return None
            return cur
        return val

    def _get_limited_options_from_param_config(param_cfg, session_obj):
        """
        Return param_cfg.options, but apply options_limit_path (e.g., Session.Params.shapesTypes) if present.
        """
        if not isinstance(param_cfg, dict):
            return []
        options = param_cfg.get('options', [])
        if not isinstance(options, list):
            return []
        limit_path = param_cfg.get('options_limit_path')
        if limit_path:
            limit_value = get_value_from_session_params(session_obj, limit_path)
            if isinstance(limit_value, (int, float)):
                limit_int = int(limit_value)
                if limit_int > 0:
                    return options[:limit_int]
        return options

    def _eval_visible_if(expr, session_obj, participant_obj=None):
        """
        Evaluate a limited visible_if expression to bool.
        Supported:
        - 'true'/'false'/bool
        - 'Session.Interaction.xxx.enabled' (tiered_checkbox)
        - "Session.Interaction.xxx.items.contains('Participant.foo')" where items can be indices or paths
        - "Participant.xxx == 'value'" for equality comparisons (e.g., "Participant.role == 'guesser'")
        """
        if expr is True or expr is False:
            return bool(expr)
        if expr is None:
            return True
        if isinstance(expr, (int, float)):
            return bool(expr)
        if not isinstance(expr, str):
            return True

        s = expr.strip()
        if s.lower() == 'true':
            return True
        if s.lower() == 'false':
            return False

        # Handle " && " (AND) - all sub-expressions must be true
        if ' && ' in s:
            parts = [p.strip() for p in s.split(' && ') if p.strip()]
            return all(_eval_visible_if(p, session_obj, participant_obj) for p in parts)

        # Handle ".contains('...')"
        if '.contains(' in s and s.endswith(')'):
            # Example: Session.Interaction.awarenessDashboard.items.contains('Participant.money')
            try:
                before_contains, contains_part = s.split('.contains(', 1)
                target_raw = contains_part[:-1].strip()  # remove trailing ')'
                if (target_raw.startswith("'") and target_raw.endswith("'")) or (
                    target_raw.startswith('"') and target_raw.endswith('"')
                ):
                    target = target_raw[1:-1]
                else:
                    target = target_raw

                # We expect something like Session.Interaction.awarenessDashboard.items
                parts = before_contains.split('.')
                if len(parts) >= 4 and parts[0] == 'Session' and parts[1] == 'Interaction':
                    # base interaction param path is first 3 parts: Session.Interaction.<paramName>
                    base_param_path = '.'.join(parts[:3] + [parts[2]])  # placeholder; overwritten below
                    # Correct reconstruction: Session.Interaction.<paramName>
                    base_param_path = f"Session.Interaction.{parts[2]}"
                    # The remaining after paramName are subkeys, e.g. ['items']
                    subkeys = parts[3:]
                    # Pull the tiered_checkbox value dict (enabled/items)
                    value_dict = _get_interaction_value(session_obj, base_param_path)
                    if not isinstance(value_dict, dict):
                        return False
                    cur = value_dict
                    for k in subkeys:
                        if isinstance(cur, dict) and k in cur:
                            cur = cur[k]
                        else:
                            return False

                    items = cur
                    if not isinstance(items, list):
                        return False

                    # Items might be list of paths OR list of indices into options
                    if any(isinstance(x, str) for x in items):
                        return target in items

                    # Indices case: map indices -> option.path using session interaction config options
                    # Prefer full interaction config (with options/paths) from experiment_config,
                    # fall back to runtime interaction state if needed.
                    interaction_cfg = None
                    if isinstance(session_obj, dict):
                        exp_cfg = session_obj.get('experiment_config')
                        if exp_cfg and isinstance(exp_cfg, dict):
                            interaction_cfg = exp_cfg.get('interaction')
                    
                    # If experiment_config.interaction is not available, try to get from top-level interaction
                    # (this happens when interaction is updated but experiment_config is not refreshed)
                    if not interaction_cfg:
                        interaction_cfg = session_obj.get('interaction') if isinstance(session_obj, dict) else None
                    
                    param_cfg = _find_interaction_param(interaction_cfg, base_param_path)
                    options = (param_cfg or {}).get('options', [])
                    
                    # If options are still not available, try to get from experiment default config
                    if not options and isinstance(session_obj, dict):
                        experiment_id = session_obj.get('experiment_type')
                        if experiment_id:
                            exp_cfg = get_experiment_by_id(experiment_id) or {}
                            exp_interaction = exp_cfg.get('interaction', {})
                            param_cfg_from_exp = _find_interaction_param(exp_interaction, base_param_path)
                            if param_cfg_from_exp:
                                options = param_cfg_from_exp.get('options', [])
                    selected_paths = []
                    for idx in items:
                        if isinstance(idx, int) and 0 <= idx < len(options):
                            opt = options[idx]
                            if isinstance(opt, dict) and opt.get('path'):
                                selected_paths.append(opt['path'])
                    
                    result = target in selected_paths
                    return result
            except Exception:
                return False

        # Handle "Participant.xxx == 'value'" equality comparisons
        if ' == ' in s:
            try:
                left_part, right_part = s.split(' == ', 1)
                left_part = left_part.strip()
                right_part = right_part.strip()
                
                # Remove quotes from right part if present
                if (right_part.startswith("'") and right_part.endswith("'")) or (
                    right_part.startswith('"') and right_part.endswith('"')
                ):
                    right_value = right_part[1:-1]
                else:
                    right_value = right_part
                
                # Check if left part is a Participant path
                if left_part.startswith('Participant.'):
                    if participant_obj:
                        left_value = _get_participant_value_by_path(participant_obj, left_part)
                        if left_value is not None:
                            return str(left_value) == str(right_value)
                    return False
            except Exception:
                return False

        # Handle simple Session.Interaction.xxx[.yyy]
        if s.startswith('Session.Interaction.'):
            parts = s.split('.')
            # base param is Session.Interaction.<paramName>
            if len(parts) >= 3:
                base_param_path = '.'.join(parts[:3])  # Session.Interaction.<paramName>
                sub = parts[3:] if len(parts) > 3 else None
                v = _get_interaction_value(session_obj, base_param_path, sub)
                return bool(v)

        # Unknown expression: default to True to avoid hiding UI unexpectedly
        return True

    experiment_id = session.get('experiment_type')
    if not experiment_id:
        return participant
    
    # Get participant config
    participant_config = get_participant_config(experiment_id, session)
    if not participant_config or len(participant_config) == 0:
        return participant
    
    participant_template = participant_config[0]
    
    # Initialize experiment_params if it doesn't exist
    if 'experiment_params' not in participant:
        participant['experiment_params'] = {}
    
    # Initialize experiment_params for each configured field based on init_path rules:
    # (1) If init_path starts with "Session.", read from session params
    # (2) If init_path is None or missing, preserve existing value or use default
    # (3) If init_path starts with "Functions.", call the corresponding function
    if 'experiment_params' in participant_template and isinstance(participant_template['experiment_params'], dict):
        for param_name, param_config in participant_template['experiment_params'].items():
            if not isinstance(param_config, dict):
                continue

            init_path = param_config.get('init_path')
            value = None
            should_update = True

            # (1) Session-based init: e.g., "Session.Params.startingMoney" or "Session.essays"
            # IMPORTANT: For fields that are initialized from session params but then modified at runtime
            # (like money), we should preserve the existing value if it exists, and only initialize
            # from session params if the field doesn't exist yet.
            # Exception: For list fields like essays, if the existing value is empty, sync from session
            if isinstance(init_path, str) and init_path.startswith('Session.'):
                existing_value = participant.get('experiment_params', {}).get(param_name)
                
                # Debug logging for essays
                if param_name == 'essays' and init_path == 'Session.essays':
                    print(f'[Participant] Processing essays field - existing_value: {existing_value}')
                    print(f'[Participant] Existing value type: {type(existing_value)}, length: {len(existing_value) if isinstance(existing_value, list) else "N/A"}')
                
                if existing_value is not None:
                    # Special case: For list fields, if existing value is empty, sync from session
                    if isinstance(existing_value, list) and len(existing_value) == 0:
                        session_value = get_value_from_session_params(session, init_path)
                        if session_value is not None and isinstance(session_value, list) and len(session_value) > 0:
                            # Merge session essays into participant essays (avoid duplicates)
                            exp_params = participant.get('experiment_params', {})
                            if param_name not in exp_params:
                                exp_params[param_name] = []
                            # Add all session items to participant (check for duplicates by essay_id or content)
                            for item in session_value:
                                if isinstance(item, dict):
                                    # For essays, check by essay_id
                                    if 'essay_id' in item:
                                        if not any(e.get('essay_id') == item.get('essay_id') for e in exp_params[param_name]):
                                            exp_params[param_name].append(item)
                                    else:
                                        # For other list items, check by content
                                        if item not in exp_params[param_name]:
                                            exp_params[param_name].append(item)
                                else:
                                    # For simple list items
                                    if item not in exp_params[param_name]:
                                        exp_params[param_name].append(item)
                            participant['experiment_params'] = exp_params
                            print(f'[Participant] Synced {len(exp_params[param_name])} essays from session (empty list case)')
                            should_update = False
                        else:
                            # Field already exists (has been modified at runtime), preserve it
                            should_update = False
                    else:
                        # Field already exists and has values, preserve it (don't overwrite)
                        # But for essays, we should still sync new ones from session
                        if param_name == 'essays' and init_path == 'Session.essays':
                            session_value = get_value_from_session_params(session, init_path)
                            if session_value is not None and isinstance(session_value, list) and len(session_value) > 0:
                                # Merge new essays from session (avoid duplicates)
                                exp_params = participant.get('experiment_params', {})
                                if param_name not in exp_params:
                                    exp_params[param_name] = []
                                added_count = 0
                                for item in session_value:
                                    if isinstance(item, dict) and 'essay_id' in item:
                                        if not any(e.get('essay_id') == item.get('essay_id') for e in exp_params[param_name]):
                                            exp_params[param_name].append(item)
                                            added_count += 1
                                if added_count > 0:
                                    participant['experiment_params'] = exp_params
                                    print(f'[Participant] Added {added_count} new essays from session (non-empty list case)')
                            should_update = False
                        else:
                            # Field already exists (has been modified at runtime), preserve it
                            should_update = False
                else:
                    # Field doesn't exist yet, initialize from session params
                    value = get_value_from_session_params(session, init_path)
                    # Debug logging for essays
                    if param_name == 'essays' and init_path == 'Session.essays':
                        print(f'[Participant] Initializing essays from session: {len(value) if isinstance(value, list) else "not a list"} items')
                        print(f'[Participant] Essays value: {value}')
                    
                    # Special handling for word_list: convert comma-separated string to list
                    if param_name == 'word_list' and init_path == 'Session.Params.wordList':
                        print(f'[Participant] Processing word_list initialization. Raw value from session: {value} (type: {type(value)})')
                        if isinstance(value, str):
                            # Split by comma and strip whitespace from each word
                            value = [word.strip() for word in value.split(',') if word.strip()]
                            print(f'[Participant] Converted wordList string to list: {value}')
                        elif isinstance(value, list):
                            # Already a list, use as is
                            print(f'[Participant] wordList is already a list: {value}')
                        else:
                            # If value is None or not a string/list, default to empty list
                            print(f'[Participant] wordList value is None or invalid, defaulting to empty list')
                            value = []

            # (2) Functions-based init: e.g., "Functions.assign_tasks"
            # IMPORTANT: For fields initialized by functions but then modified at runtime
            # (like tasks), we should preserve the existing value if it exists, and only
            # call the function if the field doesn't exist yet.
            elif isinstance(init_path, str) and init_path.startswith('Functions.'):
                existing_value = participant.get('experiment_params', {}).get(param_name)
                if existing_value is not None:
                    # Field already exists (has been modified at runtime), preserve it
                    should_update = False
                else:
                    # Field doesn't exist yet, call the function to initialize
                    func = resolve_function(init_path)
                    if func:
                        try:
                            value = func(participant, session, param_config)
                        except Exception:
                            value = None

            # (3) No init_path (or unknown pattern) -> preserve existing value or use default
            if init_path is None or not isinstance(init_path, str) or (
                not init_path.startswith('Session.') and not init_path.startswith('Functions.')
            ):
                # For fields without init_path (like in_production, inventory, production_number),
                # preserve existing runtime values - don't overwrite them!
                existing_value = participant.get('experiment_params', {}).get(param_name)
                if existing_value is not None:
                    # Field already has a value, preserve it (don't overwrite)
                    should_update = False
                else:
                    # Field doesn't exist yet, use default
                    # Special case: for 'shapes' field, if no default but has options, initialize from options
                    if param_name == 'shapes' and 'options' in param_config and isinstance(param_config.get('options'), list):
                        value = _get_limited_options_from_param_config(param_config, session)
                    else:
                        value = copy.deepcopy(param_config.get('default'))

            # Final assignment: only update if we should and have a value
            # For word_list, we want to set it even if it's an empty list (which is a valid value)
            if should_update:
                # For word_list, always set it (even if empty list or None becomes empty list)
                if param_name == 'word_list':
                    # Ensure word_list is always a list
                    if value is None:
                        value = []
                    if not isinstance(value, list):
                        value = []
                    participant['experiment_params'][param_name] = value
                    print(f'[Participant] Set word_list to: {value} (type: {type(value)}, length: {len(value)})')
                elif value is not None:
                    participant['experiment_params'][param_name] = value

    # -------- Build interface elements for frontend rendering --------
    exp_cfg = get_experiment_by_id(experiment_id) or {}
    interface_cfg = exp_cfg.get('interface', None)
    if isinstance(interface_cfg, dict):
        ui_cfg = copy.deepcopy(interface_cfg)

        # For each panel group -> list of panel configs
        filtered_ui = {}
        for group_name, panels in ui_cfg.items():
            if not isinstance(panels, list):
                continue

            new_panels = []
            for panel in panels:
                if not isinstance(panel, dict):
                    continue

                # Evaluate panel visibility
                panel_visible = _eval_visible_if(panel.get('visible_if', True), session, participant)
                if not panel_visible:
                    continue
                panel['visible_if'] = True

                # Filter/resolve bindings
                bindings = panel.get('bindings', [])
                if isinstance(bindings, list):
                    new_bindings = []
                    for b in bindings:
                        if not isinstance(b, dict):
                            continue

                        # binding-level visibility
                        if not _eval_visible_if(b.get('visible_if', True), session, participant):
                            continue
                        if 'visible_if' in b:
                            b['visible_if'] = True

                        # Resolve binding value from Participant.* path
                        if b.get('path'):
                            v = _get_participant_value_by_path(participant, b.get('path'))
                            print(f'[Participant] Resolving binding value for path: {b.get("path")}, resolved value: {v} (type: {type(v)})')
                            if v is not None:
                                b['value'] = v
                                print(f'[Participant] Set binding value to: {v}')
                            # For word_list, also set value even if it's an empty list
                            elif b.get('path') == 'Participant.word_list':
                                print(f'[Participant] word_list path resolved to None for participant {participant.get("id")}, role: {participant.get("role")}')
                                # Check if word_list exists in experiment_params
                                exp_params = participant.get('experiment_params', {})
                                if 'word_list' in exp_params:
                                    word_list_value = exp_params['word_list']
                                    print(f'[Participant] word_list found in experiment_params: {word_list_value}')
                                    b['value'] = word_list_value
                                else:
                                    print(f'[Participant] word_list NOT found in experiment_params. Available keys: {list(exp_params.keys())}')
                                    # Set to empty list as fallback
                                    b['value'] = []

                        # Resolve shape_production options if it's a Participant.* path string
                        if b.get('control') == 'shape_production' and isinstance(b.get('options'), str):
                            opt_path = b.get('options')
                            # For Participant.shapes, get options from config, not from participant instance
                            if opt_path == 'Participant.shapes':
                                # Get options from participant config
                                if 'experiment_params' in participant_template:
                                    shapes_config = participant_template['experiment_params'].get('shapes', {})
                                    if isinstance(shapes_config, dict):
                                        opt_val = _get_limited_options_from_param_config(shapes_config, session)
                                        # Set options even if it's an empty list (to replace the string path)
                                        b['options'] = opt_val if opt_val is not None else []
                            else:
                                # For other paths, try to get from participant instance
                                opt_val = _get_participant_value_by_path(participant, opt_path)
                                if opt_val is not None:
                                    b['options'] = opt_val
                        
                        # Add production count and max count for shape_production control
                        if b.get('control') == 'shape_production':
                            # Get production_number from participant (completed production count)
                            # This should be initialized to 0 by default
                            production_number = _get_participant_value_by_path(participant, 'Participant.production_number')
                            # Set countValue to production_number (defaults to 0 if not set)
                            b['countValue'] = production_number if production_number is not None else 0
                            
                            # Get maxProductionNum from session params
                            max_production = get_value_from_session_params(session, 'Session.Params.maxProductionNum')
                            if max_production is not None:
                                b['maxCount'] = int(max_production) if isinstance(max_production, (int, float)) else max_production
                        
                        # Resolve options for essay ranking form fields
                        if b.get('on_submit') == 'submit_essay_rank' and b.get('fields'):
                            fields = b.get('fields', {})
                            # Resolve essay_name field options
                            if 'essay_name' in fields:
                                essay_name_field = fields['essay_name']
                                if isinstance(essay_name_field, dict):
                                    options_path = essay_name_field.get('options')
                                    if isinstance(options_path, str) and options_path == 'Participant.essays':
                                        # Get essays from participant
                                        essays = _get_participant_value_by_path(participant, 'Participant.essays')
                                        
                                        if essays is not None and isinstance(essays, list):
                                            essay_name_field['options'] = essays
                                        else:
                                            essay_name_field['options'] = []
                        
                        # Resolve options for word_list (wordguessing experiment)
                        if b.get('control') == 'list' and b.get('path') == 'Participant.word_list':
                            options_path = b.get('options')
                            if isinstance(options_path, str) and options_path == 'Participant.word_list':
                                # Get word_list from participant
                                word_list = _get_participant_value_by_path(participant, 'Participant.word_list')
                                print(f'[Participant] Resolving word_list options. Path: {options_path}, Resolved value: {word_list} (type: {type(word_list)})')
                                
                                if word_list is not None and isinstance(word_list, list):
                                    b['options'] = word_list
                                    print(f'[Participant] Set word_list options to: {word_list}')
                                else:
                                    b['options'] = []
                                    print(f'[Participant] word_list is None or not a list, setting options to empty list')

                        new_bindings.append(b)
                    panel['bindings'] = new_bindings

                new_panels.append(panel)

            # Only keep groups with at least one visible panel
            if new_panels:
                filtered_ui[group_name] = new_panels

        participant['interface'] = filtered_ui
    
    return participant

# Register participants (updates the entire participants list)
@participant_bp.route('/api/sessions/<path:session_identifier>/participants', methods=['POST'])
def register_participants(session_identifier):
    try:
        data = request.get_json()
        if not data or 'participants' not in data:
            return jsonify({'error': 'participants array is required'}), 400
        
        participants_list = data['participants']
        if not isinstance(participants_list, list):
            return jsonify({'error': 'participants must be an array'}), 400
        
        # Check for duplicate participant names (case-insensitive)
        seen_names = set()
        for participant in participants_list:
            name = participant.get('name') or participant.get('participant_name')
            if name:
                name_lower = name.strip().lower()
                if name_lower in seen_names:
                    return jsonify({
                        'error': f'Participant name "{name}" already exists. Please use a different name.',
                        'code': 'PARTICIPANT_NAME_EXISTS'
                    }), 409
                seen_names.add(name_lower)
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        
        if not found_session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Update participants list and initialize experiment_params from session params
        for participant in participants_list:
            # Generate UUID for new participants (if id is missing or empty)
            if not participant.get('id') or participant.get('id') == '':
                participant['id'] = str(uuid.uuid4())
            
            # Sync existing essays from session to new participant (if any)
            # Sync essays if:
            # 1. The experiment type is essayranking, OR
            # 2. The session has essays (regardless of experiment type)
            experiment_type = found_session.get('experiment_type')
            session_essays = found_session.get('essays', [])
            
            if (experiment_type == 'essayranking' or (session_essays and len(session_essays) > 0)):
                exp_params = participant.get('experiment_params', {})
                if 'essays' not in exp_params:
                    exp_params['essays'] = []
                # Add all session essays to participant
                for essay in session_essays:
                    if not any(e.get('essay_id') == essay.get('essay_id') for e in exp_params['essays']):
                        exp_params['essays'].append(essay)
                participant['experiment_params'] = exp_params
            
            # Update participant's experiment_params based on init_path
            update_participant_experiment_params(participant, found_session)
            
            # Initialize agent runner if participant is an AI agent
            participant_type = participant.get('type', '').lower()
            if participant_type in ('ai', 'ai_agent'):
                experiment_type = found_session.get('experiment_type')
                if experiment_type:
                    try:
                        from agent.agent_runner import register_agent_runner
                        session_id = found_session.get('session_id') or session_key
                        participant_role = participant.get('role')  # For wordguessing
                        register_agent_runner(
                            participant_id=participant.get('id'),
                            session_id=session_id,
                            experiment_type=experiment_type,
                            participant_role=participant_role
                        )
                        # Mark agent as online when registered (even if not started yet)
                        participant['status'] = 'online'
                        print(f'[Participant] Registered agent runner for participant {participant.get("id")} ({participant.get("name") or participant.get("participant_name")}) in session {session_id}, marked as online')
                    except Exception as e:
                        print(f'[Participant] Error registering agent runner: {e}')
                        import traceback
                        traceback.print_exc()
                else:
                    # Experiment type not set yet, agent will be registered when experiment_type is set
                    # But we can still mark as online to show it's an AI participant
                    participant['status'] = 'online'
                    print(f'[Participant] AI participant {participant.get("id")} ({participant.get("name") or participant.get("participant_name")}) registered, waiting for experiment_type to be set')
        
        found_session['participants'] = participants_list
        
        # Update the session in storage
        session_module.commit_session(session_key, found_session)
        
        # Broadcast participant update via WebSocket (includes online status for agents)
        broadcast_participant_update(
            session_id=session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='full'
        )
        
        return jsonify({
            'message': 'Participants updated successfully',
            'participants': participants_list,
            'count': len(participants_list)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Get all participant info
@participant_bp.route('/api/sessions/<path:session_identifier>/participants', methods=['GET'])
def get_participants(session_identifier):
    try:
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        
        if not found_session:
            return jsonify({'error': 'Session not found'}), 404
        
        participants_list = found_session.get('participants', [])
        
        return jsonify({
            'participants': participants_list,
            'count': len(participants_list)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Start production for a participant
# NOTE: This route must be defined BEFORE the more generic PUT route below
# to ensure Flask matches the more specific route first
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/start_production', methods=['POST'])
def handle_start_production(session_identifier, participant_id):
    print(f'[DEBUG] handle_start_production called: session={session_identifier}, participant={participant_id}')
    try:
        data = request.get_json()
        print(f'[DEBUG] Request data: {data}')
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        shape = data.get('shape')
        if not shape:
            return jsonify({'success': False, 'error': 'Shape is required'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        participants_list = found_session.get('participants', [])
        
        # Find participant
        participant = None
        participant_index = None
        for i, p in enumerate(participants_list):
            if p.get('id') == participant_id:
                participant = p
                participant_index = i
                break
        
        if not participant:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
        
        # Call start_production function
        result = start_production(participant, found_session, shape)
        
        if not result.get('success'):
            return jsonify(result), 400
        
        # Recalculate interface config after updating experiment_params
        # This ensures frontend gets updated values for money, production count, etc.
        update_participant_experiment_params(participant, found_session)
        
        # Update participant in session
        participants_list[participant_index] = participant
        found_session['participants'] = participants_list
        session_module.commit_session(session_key, found_session)
        
        # Broadcast participant update via WebSocket
        broadcast_participant_update(
            session_id=found_session.get('session_id') or session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='partial'
        )
        
        # Action log
        _log_human_action(
            session_key, found_session, participant_id, 'start_production',
            f"produce {shape}", result='success',
            metadata={'shape': shape}, data=data,
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Submit shape for order fulfillment
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/submit_shape', methods=['POST'])
def handle_submit_shape(session_identifier, participant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        shape = data.get('shape')
        if not shape:
            return jsonify({'success': False, 'error': 'Shape is required'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        participants_list = found_session.get('participants', [])
        
        # Find participant
        participant = None
        participant_index = None
        for i, p in enumerate(participants_list):
            if p.get('id') == participant_id:
                participant = p
                participant_index = i
                break
        
        if not participant:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
        
        # Get participant experiment params
        exp_params = participant.get('experiment_params', {})
        inventory = exp_params.get('inventory', [])
        tasks = exp_params.get('tasks', [])
        
        # Ensure inventory is a list
        if not isinstance(inventory, list):
            inventory = []
        
        # Ensure tasks is a list
        if not isinstance(tasks, list):
            tasks = []
        
        # Check if participant has the shape in inventory
        if shape not in inventory:
            return jsonify({
                'success': False,
                'error': f'Shape {shape} not in inventory',
                'has_shape': False
            }), 400
        
        # Get incentive money from session params
        incentive_money = get_value_from_session_params(found_session, 'Session.Params.incentiveMoney')
        incentive_money = int(incentive_money) if incentive_money is not None else 60
        
        # Remove shape from inventory
        inventory.remove(shape)
        exp_params['inventory'] = inventory
        
        # Remove the fulfilled order from tasks (remove first occurrence of the shape)
        if shape in tasks:
            tasks.remove(shape)
        exp_params['tasks'] = tasks
        
        # Add incentive money
        current_money = exp_params.get('money', 0)
        exp_params['money'] = current_money + incentive_money
        
        # Update order progress (increment by 1)
        current_order_progress = exp_params.get('order_progress', 0)
        exp_params['order_progress'] = current_order_progress + 1
        
        # Update participant
        participant['experiment_params'] = exp_params
        participants_list[participant_index] = participant
        found_session['participants'] = participants_list
        session_module.commit_session(session_key, found_session)
        
        # Recalculate interface config after updating experiment_params
        update_participant_experiment_params(participant, found_session)
        
        # Broadcast participant update via WebSocket
        broadcast_participant_update(
            session_id=found_session.get('session_id') or session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='partial'
        )
        
        return jsonify({
            'success': True,
            'message': f'Successfully fulfilled {shape} order',
            'shape': shape,
            'incentive_money': incentive_money,
            'new_money': exp_params['money'],
            'new_order_progress': exp_params['order_progress']
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Update one participant's info
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>', methods=['PUT'])
def update_participant(session_identifier, participant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        
        if not found_session:
            return jsonify({'error': 'Session not found'}), 404
        
        participants_list = found_session.get('participants', [])
        
        # Check for duplicate name when updating (exclude current participant)
        new_name = data.get('name') or data.get('participant_name')
        if new_name:
            new_name_lower = new_name.strip().lower()
            for p in participants_list:
                if p.get('id') != participant_id:
                    existing_name = p.get('name') or p.get('participant_name')
                    if existing_name and existing_name.strip().lower() == new_name_lower:
                        return jsonify({
                            'error': f'Participant name "{new_name}" already exists. Please use a different name.',
                            'code': 'PARTICIPANT_NAME_EXISTS'
                        }), 409
        
        # Find and update participant
        participant_found = False
        # Extract action log fields (don't persist to participant)
        log_data = {'screenshot': data.get('screenshot'), 'html_snapshot': data.get('html_snapshot')}
        update_data = {k: v for k, v in data.items() if k not in ('screenshot', 'html_snapshot')}
        for i, participant in enumerate(participants_list):
            if participant.get('id') == participant_id:
                # Update participant fields (exclude screenshot/html_snapshot)
                participants_list[i].update(update_data)
                # Update participant's experiment_params based on init_path
                update_participant_experiment_params(participants_list[i], found_session)
                participant_found = True
                # Check for vote updates (initial_vote, final_vote)
                exp_params = data.get('experiment_params', {})
                if isinstance(exp_params, dict):
                    if 'initial_vote' in exp_params and exp_params['initial_vote'] not in (None, 'none'):
                        _log_human_action(
                            session_key, found_session, participant_id, 'submit_initial_vote',
                            str(exp_params['initial_vote']), result='success',
                            metadata={'selected': exp_params['initial_vote']}, data=log_data, page='vote_dialog',
                        )
                    if 'final_vote' in exp_params and exp_params['final_vote'] not in (None, 'none'):
                        _log_human_action(
                            session_key, found_session, participant_id, 'submit_final_vote',
                            str(exp_params['final_vote']), result='success',
                            metadata={'selected': exp_params['final_vote']}, data=log_data, page='vote_dialog',
                        )
                break
        
        if not participant_found:
            return jsonify({'error': 'Participant not found'}), 404
        
        # Update session
        found_session['participants'] = participants_list
        
        session_module.commit_session(session_key, found_session)
        
        # Broadcast participant update via WebSocket
        broadcast_participant_update(
            session_id=session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='partial'
        )
        
        return jsonify({
            'message': 'Participant updated successfully',
            'participant': participants_list[i]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Transcribe audio using OpenAI Whisper (supports Azure OpenAI)
@participant_bp.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    """Transcribe audio file to text using OpenAI Whisper API (OpenAI or Azure OpenAI)."""
    try:
        if 'audio' not in request.files and 'file' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files.get('audio') or request.files.get('file')
        if not audio_file or audio_file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400
        
        # Azure OpenAI: use endpoint + api_key + deployment
        azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '').strip()
        azure_key = os.getenv('AZURE_OPENAI_API_KEY', '').strip()
        azure_deployment = (
            os.getenv('AZURE_WHISPER_DEPLOYMENT') or
            os.getenv('AZURE_DEPLOYMENT_ID') or
            os.getenv('AZURE_WHISPER_DEPLOYMENT', 'whisper')
        ).strip()
        azure_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-01').strip()
        
        # Standard OpenAI
        openai_key = os.getenv('OPENAI_API_KEY', '').strip()
        
        use_azure = azure_endpoint and azure_key and azure_deployment
        
        if not use_azure and not openai_key:
            return jsonify({
                'error': 'Transcription not configured. Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_WHISPER_DEPLOYMENT (or AZURE_DEPLOYMENT_ID) for Azure; or OPENAI_API_KEY for OpenAI.'
            }), 503
        
        # Save to temp file (Whisper API needs file path or file-like object)
        ext = os.path.splitext(audio_file.filename)[1] or '.webm'
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            from openai import OpenAI, AzureOpenAI
            
            if use_azure:
                client = AzureOpenAI(
                    api_key=azure_key,
                    api_version=azure_version,
                    azure_endpoint=azure_endpoint.rstrip('/')
                )
                model = azure_deployment
            else:
                client = OpenAI(api_key=openai_key)
                model = 'whisper-1'
            
            with open(tmp_path, 'rb') as f:
                transcription = client.audio.transcriptions.create(
                    model=model,
                    file=f,
                    response_format='text'
                )
            # Handle both string (plain text) and Transcription object
            if isinstance(transcription, str):
                text = transcription
            else:
                text = getattr(transcription, 'text', None) or str(transcription) if transcription else ''
            return jsonify({'text': (text or '').strip(), 'success': True})
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


# Upload audio for voice messages (returns URL for playback)
@participant_bp.route('/api/upload_audio', methods=['POST'])
def upload_audio():
    """Upload audio file and return URL for message storage."""
    try:
        if 'audio' not in request.files and 'file' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        audio_file = request.files.get('audio') or request.files.get('file')
        if not audio_file or audio_file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'audio')
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(audio_file.filename)[1] or '.webm'
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(upload_dir, unique_name)
        audio_file.save(file_path)
        url = f'/api/audio/{unique_name}'
        return jsonify({'url': url, 'success': True, 'filename': unique_name})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@participant_bp.route('/api/audio/<filename>', methods=['GET'])
def serve_audio(filename):
    """Serve uploaded audio file."""
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'audio')
    return send_from_directory(upload_dir, filename)


# handle participant login
@participant_bp.route('/api/auth/login', methods=['POST'])
def handle_participant_login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        participant_name = data.get('participant_name')
        session_name = data.get('session_name')
        
        # Validate input
        if not participant_name or not participant_name.strip():
            return jsonify({'success': False, 'message': 'Participant name is required'}), 400
        
        if not session_name or not session_name.strip():
            return jsonify({'success': False, 'message': 'Session name is required'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_name.strip())
        
        if not found_session:
            return jsonify({'success': False, 'message': 'Session not found'}), 404
        
        # Find participant
        participant = find_participant_by_name(participant_name.strip(), found_session)
        
        if not participant:
            return jsonify({'success': False, 'message': 'Participant not found in this session'}), 404
        
        # Verify participant type is 'human' (only human participants can login)
        participant_type = participant.get('type', '').lower()
        if participant_type != 'human':
            return jsonify({
                'success': False, 
                'message': 'Only human participants can login. This participant is of type: ' + participant.get('type', 'unknown')
            }), 403
        
        # Generate a simple token (in production, use JWT or similar)
        # For now, we'll use a combination of session_id and participant_id
        token = f"{session_key}:{participant.get('id', '')}"

        # Update participant's login_time to current timestamp
        participant['login_time'] = datetime.now().isoformat()
        
        # Ensure participant has up-to-date experiment params + computed interface config
        # (participant is a reference to the session participant object)
        update_participant_experiment_params(participant, found_session)
        
        # Update the session in storage (participant is already updated by reference)
        session_module.commit_session(session_key, found_session)
        
        # Broadcast participant update via WebSocket to notify all clients (including researcher interface)
        # Use session_id (UUID) if available, otherwise fall back to session_key
        broadcast_session_id = found_session.get('session_id') or session_key
        participants_list = found_session.get('participants', [])
        broadcast_participant_update(
            session_id=broadcast_session_id,
            participants=participants_list,
            session_info=found_session,
            update_type='partial'
        )
        
        # Prepare response data
        # Ensure participant has participant_id field for frontend compatibility
        participant_response = participant.copy()
        if 'id' in participant_response:
            participant_response['participant_id'] = participant_response['id']
        
        # Prepare session response
        session_response = {
            'session_id': found_session.get('session_id'),
            'session_code': found_session.get('session_name'),  # For frontend compatibility
            'session_name': found_session.get('session_name'),
            'experiment_type': found_session.get('experiment_type'),
            'status': found_session.get('status')
        }
        
        return jsonify({
            'success': True,
            'token': token,
            'participant': participant_response,
            'session': session_response
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Update map_progress (Map Task: follower's drawing state for guider awareness)
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/map_progress', methods=['POST'])
def update_map_progress(session_identifier, participant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        if found_session.get('experiment_type') != 'maptask':
            return jsonify({'success': False, 'error': 'Map progress only applies to Map Task sessions'}), 400

        participants_list = found_session.get('participants', [])
        participant = None
        for p in participants_list:
            if p.get('id') == participant_id:
                participant = p
                break

        if not participant:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404

        if participant.get('role') != 'follower':
            return jsonify({'success': False, 'error': 'Only follower can update map progress'}), 403

        map_progress = data.get('map_progress')
        if not isinstance(map_progress, dict):
            return jsonify({'success': False, 'error': 'map_progress must be an object'}), 400

        if 'experiment_params' not in participant:
            participant['experiment_params'] = {}
        participant['experiment_params']['map_progress'] = map_progress

        session_module.commit_session(session_key, found_session)

        broadcast_session_id = found_session.get('session_id') or session_key
        broadcast_participant_update(
            session_id=broadcast_session_id,
            participants=participants_list,
            session_info=found_session,
            update_type='partial'
        )

        return jsonify({'success': True, 'map_progress': map_progress}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Log action from frontend (e.g. map tool clicks, draw stop)
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/log_action', methods=['POST'])
def log_action_endpoint(session_identifier, participant_id):
    """Log a client-side action (e.g. map task tool clicks)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        action_type = data.get('action_type')
        action_content = data.get('action_content', '')
        if not action_type:
            return jsonify({'success': False, 'error': 'action_type is required'}), 400

        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        participant = next((p for p in found_session.get('participants', []) if p.get('id') == participant_id), None)
        if not participant:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
        if (participant.get('type') or '').lower() in ('ai', 'ai_agent'):
            return jsonify({'success': False, 'error': 'Only human participants can log client actions'}), 403

        actual_session_id = found_session.get('session_id') or session_key
        from services.action_logger import log_action
        action_id = log_action(
            session_id=actual_session_id,
            participant_id=participant_id,
            is_human=True,
            action_type=action_type,
            action_content=action_content,
            result=data.get('result', 'success'),
            metadata=data.get('metadata', {}),
            page=data.get('page', 'map_task'),
            experiment_type=found_session.get('experiment_type', ''),
            screenshot=data.get('screenshot'),
            html_snapshot=data.get('html_snapshot'),
            map_image=data.get('map_image'),
            session=found_session,
            participant=participant,
        )
        # In-session annotation: trigger on draw stop when annotation enabled
        if action_type == 'map_draw_stop':
            try:
                from services.annotation_service import (
                    should_trigger_annotation,
                    trigger_annotation,
                )
                should_trigger, checkpoint = should_trigger_annotation(
                    session_key, found_session, participant_id, 'draw_stop'
                )
                if should_trigger and checkpoint is not None:
                    trigger_annotation(session_key, found_session, checkpoint, sessions)
            except Exception as ann_err:
                print(f'[Annotation] Error checking/triggering after draw stop: {ann_err}')
        return jsonify({'success': True, 'action_id': action_id}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Submit annotation (in-session annotation checkpoint)
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/submit_annotation', methods=['POST'])
def submit_annotation(session_identifier, participant_id):
    """Submit annotation response for in-session checkpoint. Resumes session when all humans have submitted."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        transcription = (data.get('transcription') or '').strip()
        if not transcription:
            return jsonify({'success': False, 'error': 'transcription is required'}), 400

        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        if not found_session.get('annotation_active'):
            return jsonify({'success': False, 'error': 'No annotation checkpoint active'}), 400

        participant = next((p for p in found_session.get('participants', []) if p.get('id') == participant_id), None)
        if not participant:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
        if (participant.get('type') or '').lower() in ('ai', 'ai_agent'):
            return jsonify({'success': False, 'error': 'Only human participants can submit annotations'}), 403

        from services.annotation_service import submit_annotation as annotation_submit
        resumed = annotation_submit(session_key, found_session, participant_id, transcription, sessions)
        return jsonify({'success': True, 'resumed': resumed}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Serve log files (screenshots, map images, audio) for a session
@participant_bp.route('/api/sessions/<path:session_identifier>/log_files/<path:filename>', methods=['GET'])
def serve_log_file(session_identifier, filename):
    """Serve a file from logs/{session_id}/files/ (e.g. screenshots, map images, audio)."""
    try:
        from services.action_logger import LOGS_BASE_DIR
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_data_dir = os.path.join(backend_dir, 'sample_annotation_data')

        from urllib.parse import unquote
        session_identifier = unquote(session_identifier)
        session_key, found_session = find_session_by_identifier(session_identifier)
        actual_session_id = found_session.get('session_id') or session_key if found_session else session_identifier

        # Try logs first
        files_dir = os.path.join(LOGS_BASE_DIR, actual_session_id, 'files')
        file_path = os.path.join(files_dir, filename)
        if os.path.isfile(file_path) and os.path.realpath(file_path).startswith(os.path.realpath(files_dir)):
            return send_from_directory(files_dir, filename)

        # Fallback: sample_annotation_data for dev/testing
        sample_files_dir = os.path.join(sample_data_dir, 'files')
        sample_file_path = os.path.join(sample_files_dir, filename)
        if os.path.isfile(sample_file_path) and os.path.realpath(sample_file_path).startswith(os.path.realpath(sample_files_dir)):
            return send_from_directory(sample_files_dir, filename)

        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Post-session annotation: get merged logs and annotation moments
@participant_bp.route('/api/sessions/<path:session_identifier>/post_annotation_data', methods=['GET'])
def get_post_annotation_data(session_identifier):
    """Return merged interaction logs and annotation moments for post-session annotation."""
    try:
        import json
        from services.action_logger import LOGS_BASE_DIR
        from urllib.parse import unquote
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_data_dir = os.path.join(backend_dir, 'sample_annotation_data')

        session_id = unquote(session_identifier)
        participant_id = request.args.get('participant_id')
        if not participant_id:
            return jsonify({'error': 'participant_id is required'}), 400

        # Resolve session - may use sample data
        session_key, found_session = find_session_by_identifier(session_id)
        use_sample = False
        logs_dir = os.path.join(LOGS_BASE_DIR, session_id)
        if not os.path.isdir(logs_dir):
            sample_logs_dir = sample_data_dir
            if os.path.isdir(sample_logs_dir):
                use_sample = True
                logs_dir = sample_logs_dir

        # Collect participant IDs from jsonl files in logs dir
        participant_ids = []
        if os.path.isdir(logs_dir):
            for f in os.listdir(logs_dir):
                if f.endswith('.jsonl') and f != 'files':
                    pid = f[:-6]  # strip .jsonl
                    participant_ids.append(pid)

        # If no jsonl in logs, use sample participant IDs
        if not participant_ids and use_sample:
            participant_ids = ['a59bed79-e55a-417e-92cc-e0ff70fc8cf9', 'b6adf54e-f7e9-41f7-af48-a605c95f3d20']

        # Load and merge all logs (local jsonl first, then PostgreSQL if empty)
        all_entries = []
        for pid in participant_ids:
            log_path = os.path.join(logs_dir, f'{pid}.jsonl')
            if not os.path.isfile(log_path):
                continue
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        all_entries.append(entry)
            except Exception as e:
                print(f'[PostAnnotation] Error reading {log_path}: {e}')

        if not all_entries:
            try:
                from services.db import load_session_logs
                all_entries = load_session_logs(session_id)
            except Exception as e:
                print(f'[PostAnnotation] DB load: {e}')

        # Sort by timestamp
        all_entries.sort(key=lambda e: e.get('timestamp', ''))

        # Filter out initial system auto-generated reset actions for map task follower
        # These are the first reset actions that happen when the session just started
        filtered_entries = all_entries
        if found_session and found_session.get('experiment_type') == 'maptask':
            # Find first non-reset action for each participant, keep resets before that
            participant_first_action = {}
            for e in all_entries:
                pid = e.get('participant_id')
                if pid and pid not in participant_first_action:
                    if e.get('action_type') != 'map_tool_click' or e.get('action_content') != 'reset':
                        participant_first_action[pid] = e
            # Filter: keep resets only if they appear before participant's first real action
            filtered_entries = []
            for e in all_entries:
                pid = e.get('participant_id')
                is_reset = e.get('action_type') == 'map_tool_click' and e.get('action_content') == 'reset'
                if is_reset and pid:
                    first_action = participant_first_action.get(pid)
                    if first_action:
                        e_time = e.get('timestamp', '')
                        f_time = first_action.get('timestamp', '')
                        if e_time < f_time:
                            continue  # Skip this auto-generated reset
                filtered_entries.append(e)

        # Build participant name map (from session or defaults)
        participant_names = {}
        if found_session:
            for p in found_session.get('participants', []):
                pid = p.get('id') or p.get('participant_id')
                name = p.get('name') or p.get('participant_name')
                role = (p.get('experiment_params') or {}).get('role', '')
                if pid:
                    participant_names[pid] = name or role or pid[:8]
        for pid in participant_ids:
            if pid not in participant_names:
                participant_names[pid] = pid[:8] + '...'

        try:
            from services.s3_storage import resolve_s3_fields_in_entry
            filtered_entries = [resolve_s3_fields_in_entry(dict(e)) for e in filtered_entries]
        except Exception as ex:
            print(f'[PostAnnotation] S3 resolve: {ex}')

        # Annotation moments: current participant's actions that have screenshots (from filtered, after S3 presign)
        annotation_moments = [e for e in filtered_entries if e.get('participant_id') == participant_id and e.get('screenshot')]

        # Base URL for log files (local files/ paths); s3:// assets are expanded to presigned HTTPS above
        files_base = f'/api/sessions/{session_id}/log_files'

        # Get session name - try from session, or from first log entry
        session_name = ''
        if found_session:
            session_name = found_session.get('session_name', '')
        # If no session_name found, try to get from first log entry
        if not session_name and all_entries:
            session_name = all_entries[0].get('session_name', '')

        # Post-session saved answers: PostgreSQL first, then local JSON fallback
        saved_annotations = {}
        try:
            from services.db import load_post_session_annotations

            db_saved = load_post_session_annotations(session_id, participant_id)
            if db_saved:
                saved_annotations = db_saved
        except Exception as e:
            print(f'[PostAnnotation] DB post_annotations: {e}')
        if not saved_annotations:
            ann_path = os.path.join(LOGS_BASE_DIR, session_id, f'post_annotations_{participant_id}.json')
            if os.path.isfile(ann_path):
                try:
                    with open(ann_path, 'r', encoding='utf-8') as f:
                        saved_annotations = json.load(f)
                except Exception as e:
                    print(f'[PostAnnotation] Error reading annotations file: {e}')

        in_session_annotations = []
        try:
            from services.db import load_in_session_annotations

            in_session_annotations = load_in_session_annotations(session_id, participant_id)
        except Exception as e:
            print(f'[PostAnnotation] DB in_session: {e}')

        # Fallback: in-memory session snapshot (no DB / dev) has annotation_data
        if not in_session_annotations and found_session:
            raw = (found_session.get('annotation_data') or {}).get(participant_id)
            if isinstance(raw, list) and raw:
                for item in sorted(raw, key=lambda x: x.get('checkpoint', 0)):
                    in_session_annotations.append(
                        {
                            'checkpoint_index': item.get('checkpoint'),
                            'transcription': (item.get('transcription') or ''),
                            'created_at': item.get('created_at') or '',
                        }
                    )

        # Session timing for post-annotation UI (progress % of action vs duration)
        session_duration_seconds = None
        session_started_at = None
        if found_session:
            session_started_at = found_session.get('started_at')
            dm = get_value_from_session_params(found_session, 'Session.Params.duration')
            if dm is None:
                dm = found_session.get('duration_minutes')
            if dm is not None:
                try:
                    session_duration_seconds = int(float(dm)) * 60
                except (TypeError, ValueError):
                    session_duration_seconds = None

        saved_annotation_asset_urls = {}
        try:
            from services.s3_storage import presign_saved_annotation_asset_urls

            saved_annotation_asset_urls = presign_saved_annotation_asset_urls(saved_annotations)
        except Exception as e:
            print(f'[PostAnnotation] presign saved assets: {e}')

        return jsonify({
            'merged_logs': filtered_entries,
            'annotation_moments': annotation_moments,
            'saved_annotations': saved_annotations,
            'saved_annotation_asset_urls': saved_annotation_asset_urls,
            'in_session_annotations': in_session_annotations,
            'participant_names': participant_names,
            'files_base': files_base,
            'session_id': session_id,
            'session_name': session_name,
            'session_duration_seconds': session_duration_seconds,
            'session_started_at': session_started_at,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Post-session annotation: save annotations to local file
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/post_annotations', methods=['POST', 'PUT'])
def save_post_annotations(session_identifier, participant_id):
    """Save post-session annotations to logs/{session_id}/post_annotations_{participant_id}.json"""
    try:
        import json
        from services.action_logger import LOGS_BASE_DIR
        from urllib.parse import unquote

        session_id = unquote(session_identifier)
        data = request.get_json()
        if not data or 'annotations' not in data:
            return jsonify({'error': 'annotations object required'}), 400

        annotations = data.get('annotations', {})
        session_dir = os.path.join(LOGS_BASE_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        ann_path = os.path.join(session_dir, f'post_annotations_{participant_id}.json')

        with open(ann_path, 'w', encoding='utf-8') as f:
            json.dump(annotations, f, ensure_ascii=False, indent=2)

        try:
            from services.db import upsert_post_session_annotations

            upsert_post_session_annotations(session_id, participant_id, annotations)
        except Exception as db_err:
            print(f'[PostAnnotation] DB upsert post_annotations: {db_err}')

        return jsonify({'success': True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Presigned S3 PUT for post-session annotation assets (browser uploads directly to S3; bytes do not pass through this app)
@participant_bp.route(
    '/api/sessions/<path:session_identifier>/participants/<participant_id>/post_annotation_presign',
    methods=['POST'],
)
def post_annotation_presign(session_identifier, participant_id):
    try:
        import re
        from urllib.parse import unquote

        from services import s3_storage

        session_id = unquote(session_identifier)
        data = request.get_json() or {}
        action_id = (data.get('action_id') or '').strip()
        asset = (data.get('asset') or '').strip()
        content_type = (data.get('content_type') or '').strip() or 'application/octet-stream'

        uuid_pat = re.compile(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        )
        if not uuid_pat.match(action_id):
            return jsonify({'error': 'action_id must be a UUID'}), 400
        if asset not in ('screenshot', 'html_snapshot'):
            return jsonify({'error': 'asset must be screenshot or html_snapshot'}), 400

        if asset == 'screenshot':
            filename = 'screenshot.jpg'
            if 'image/' not in content_type:
                content_type = 'image/jpeg'
        else:
            filename = 'html_snapshot.html'
            if 'html' not in content_type and 'text/' not in content_type:
                content_type = 'text/html; charset=utf-8'

        if not s3_storage.is_s3_configured():
            return jsonify({'error': 'S3 is not configured on the server'}), 503

        key = s3_storage.build_post_annotation_asset_key(session_id, participant_id, action_id, filename)
        upload_url = s3_storage.presign_put_url(key, content_type)
        if not upload_url:
            return jsonify({'error': 'Could not create upload URL'}), 500
        s3_uri = s3_storage.s3_uri_for_key(key)
        view_url = s3_storage.presign_get_url(s3_uri)
        return jsonify(
            {
                'upload_url': upload_url,
                's3_uri': s3_uri,
                'key': key,
                'method': 'PUT',
                'view_url': view_url,
            }
        ), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Submit trade offer
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/submit_trade', methods=['POST'])
def submit_trade(session_identifier, participant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Find participant
        participants_list = found_session.get('participants', [])
        from_participant = None
        for p in participants_list:
            if p.get('id') == participant_id:
                from_participant = p
                break
        
        if not from_participant:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
        
        # Get trade data - support flexible item structure
        trade_action = data.get('trade_action', 'buy')  # 'buy' or 'sell'
        to_participant_id = data.get('to_participant')
        price = float(data.get('trade_price', 0))
        
        # Support both old format (shape) and new flexible format (trade_item)
        trade_item = data.get('trade_item') or data.get('shape')  # Backward compatible
        item_type = data.get('item_type', 'shape')  # Default to 'shape' for backward compatibility
        quantity = int(data.get('quantity', 1))
        
        if not to_participant_id:
            return jsonify({'success': False, 'error': 'to_participant is required'}), 400
        
        if not trade_item and item_type != 'price_only':  # Allow price-only trades
            return jsonify({'success': False, 'error': 'trade_item is required'}), 400
        
        # Find to_participant
        to_participant = None
        for p in participants_list:
            if p.get('id') == to_participant_id:
                to_participant = p
                break
        
        if not to_participant:
            return jsonify({'success': False, 'error': 'Target participant not found'}), 404
        
        # Get experiment config to determine validation rules
        experiment_type = found_session.get('experiment_type', '')
        experiment_config = found_session.get('experiment_config', {})
        
        # Validate trade action - flexible validation based on item_type
        if item_type != 'price_only':  # Only validate inventory if there's an item
            if trade_action == 'sell':
                # From is selling to To - check if seller has the item in inventory
                exp_params = from_participant.get('experiment_params', {})
                inventory = exp_params.get('inventory', [])
                
                # Check if item exists in inventory (support both list and dict formats)
                has_item = False
                if isinstance(inventory, list):
                    # For list format: check if item is in list
                    if item_type == 'shape':
                        has_item = trade_item in inventory
                    else:
                        # For other types, check if item dict matches
                        has_item = any(
                            (isinstance(item, dict) and item.get('type') == item_type and item.get('value') == trade_item) or
                            (not isinstance(item, dict) and item == trade_item)
                            for item in inventory
                        )
                
                if not has_item:
                    item_display = trade_item if isinstance(trade_item, str) else str(trade_item)
                    return jsonify({'success': False, 'error': f'You do not have {item_display} in your inventory'}), 400
                
                # Check if buyer (to_participant) has enough money
                to_exp_params = to_participant.get('experiment_params', {})
                buyer_money = to_exp_params.get('money', 0)
                if buyer_money < price:
                    return jsonify({'success': False, 'error': 'Buyer does not have enough money'}), 400
                    
            elif trade_action == 'buy':
                # From is buying from To
                # Note: We don't check seller's inventory at propose stage, only at accept stage
                # Check if buyer (from_participant) has enough money
                from_exp_params = from_participant.get('experiment_params', {})
                buyer_money = from_exp_params.get('money', 0)
                if buyer_money < price:
                    return jsonify({'success': False, 'error': 'You do not have enough money'}), 400
        else:
            # Price-only trade: only validate money
            if trade_action == 'buy':
                from_exp_params = from_participant.get('experiment_params', {})
                buyer_money = from_exp_params.get('money', 0)
                if buyer_money < price:
                    return jsonify({'success': False, 'error': 'You do not have enough money'}), 400
            elif trade_action == 'sell':
                to_exp_params = to_participant.get('experiment_params', {})
                buyer_money = to_exp_params.get('money', 0)
                if buyer_money < price:
                    return jsonify({'success': False, 'error': 'Buyer does not have enough money'}), 400
        
        # Initialize trade data structures if they don't exist
        if 'pending_offers' not in found_session:
            found_session['pending_offers'] = []
        if 'completed_trades' not in found_session:
            found_session['completed_trades'] = []
        
        # Create trade offer - flexible structure
        offer_id = str(uuid.uuid4())
        offer = {
            'id': offer_id,
            'from': participant_id,
            'to': to_participant_id,
            'offer_type': trade_action,  # 'buy' or 'sell'
            'item_type': item_type,
            'quantity': quantity,
            'price': price,
            'status': 'pending',
            'timestamp': datetime.now().isoformat()
        }
        
        # Add item data based on type (backward compatible with 'shape' field)
        if trade_item:
            offer['trade_item'] = trade_item
            if item_type == 'shape':
                offer['shape'] = trade_item  # Backward compatibility
        elif item_type == 'price_only':
            offer['trade_item'] = None
        
        # Add to pending offers
        found_session['pending_offers'].append(offer)
        session_module.commit_session(session_key, found_session)
        
        # Broadcast update to both participants
        broadcast_participant_update(
            session_id=session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='trade_update'
        )
        
        # Action log
        _log_human_action(
            session_key, found_session, participant_id, 'submit_trade',
            f"{trade_action} {trade_item or 'price_only'} to {to_participant.get('name', to_participant_id)} @ ${price}",
            result='success',
            metadata={'offer_id': offer_id, 'to_participant': to_participant_id, 'trade_action': trade_action, 'price': price},
            data=data,
        )
        
        return jsonify({
            'success': True,
            'offer_id': offer_id,
            'offer': offer
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Submit investment for daytrader experiment
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/submit_investment', methods=['POST'])
def submit_investment(session_identifier, participant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Find participant
        participants_list = found_session.get('participants', [])
        participant = None
        for p in participants_list:
            if p.get('id') == participant_id:
                participant = p
                break
        
        if not participant:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
        
        # Get investment data
        investment_amount = float(data.get('investment_amount', 0))
        investment_type = data.get('investment_type', 'individual')
        
        # Validate investment_amount
        if investment_amount <= 0:
            return jsonify({'success': False, 'error': 'Investment amount must be greater than 0'}), 400
        
        if investment_type not in ['individual', 'group']:
            return jsonify({'success': False, 'error': 'Invalid investment type. Must be individual or group'}), 400
        
        # Get participant's current money
        exp_params = participant.get('experiment_params', {})
        current_money = exp_params.get('money', 0)
        
        # Check if participant has enough money
        if current_money < investment_amount:
            return jsonify({'success': False, 'error': f'Insufficient funds. Need ${investment_amount}, have ${current_money}'}), 400
        
        # Initialize investment_history if it doesn't exist
        if 'investment_history' not in exp_params:
            exp_params['investment_history'] = []
        
        # Ensure investment_history is a list
        if not isinstance(exp_params['investment_history'], list):
            exp_params['investment_history'] = []
        
        # Create investment record
        investment_record = {
            'id': str(uuid.uuid4()),
            'investment_amount': investment_amount,
            'investment_type': investment_type,
            'timestamp': datetime.now().isoformat(),
            'money_before': current_money,
            'money_after': current_money - investment_amount
        }
        
        # Add to investment history
        exp_params['investment_history'].append(investment_record)
        
        # Deduct money
        exp_params['money'] = current_money - investment_amount
        
        # Update participant
        participant['experiment_params'] = exp_params
        
        # Recompute interface to ensure frontend gets updated data (especially money and investment_history)
        update_participant_experiment_params(participant, found_session)
        
        # Update session (important: update the participant in the list)
        # Find and update the participant in the list to ensure consistency
        for i, p in enumerate(participants_list):
            if p.get('id') == participant_id:
                participants_list[i] = participant
                break
        
        found_session['participants'] = participants_list
        session_module.commit_session(session_key, found_session)
        
        # Log the update for debugging
        print(f'[submit_investment] Updated participant {participant_id}:')
        print(f'  - Money: ${current_money} -> ${exp_params["money"]}')
        print(f'  - Investment history count: {len(exp_params["investment_history"])}')
        print(f'  - Latest investment: {investment_record}')
        
        # Broadcast update to all participants
        broadcast_participant_update(
            session_id=session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='investment_update'
        )
        
        # Action log
        _log_human_action(
            session_key, found_session, participant_id, 'submit_investment',
            f"${investment_amount} ({investment_type})",
            result='success',
            metadata={'investment_id': investment_record['id'], 'investment_type': investment_type, 'amount': investment_amount},
            data=data,
        )
        
        return jsonify({
            'success': True,
            'investment_id': investment_record['id'],
            'investment': investment_record,
            'remaining_money': exp_params['money'],
            'investment_history_count': len(exp_params['investment_history'])
        }), 200
        
    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid investment amount: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Get pending offers for a session
@participant_bp.route('/api/sessions/<path:session_identifier>/pending_offers', methods=['GET'])
def get_pending_offers(session_identifier):
    try:
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Get pending offers
        pending_offers = found_session.get('pending_offers', [])
        
        # Filter out cancelled/declined offers (only show pending)
        active_offers = [o for o in pending_offers if o.get('status') == 'pending']
        
        return jsonify({
            'success': True,
            'offers': active_offers
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Get completed trades for a session
@participant_bp.route('/api/sessions/<path:session_identifier>/completed_trades', methods=['GET'])
def get_completed_trades(session_identifier):
    try:
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Get completed trades
        completed_trades = found_session.get('completed_trades', [])
        
        return jsonify({
            'success': True,
            'trades': completed_trades
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Respond to trade offer (accept/decline)
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/respond_to_offer', methods=['POST'])
def respond_to_offer(session_identifier, participant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        offer_id = data.get('offer_id')
        response = data.get('response')  # 'accept' or 'decline'
        
        if not offer_id or response not in ['accept', 'decline']:
            return jsonify({'success': False, 'error': 'offer_id and response (accept/decline) are required'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        participants_list = found_session.get('participants', [])
        pending_offers = found_session.get('pending_offers', [])
        
        # Find the offer
        offer = None
        offer_index = None
        for i, o in enumerate(pending_offers):
            if o.get('id') == offer_id:
                offer = o
                offer_index = i
                break
        
        if not offer:
            return jsonify({'success': False, 'error': 'Offer not found'}), 404
        
        # Verify participant is the recipient
        if offer.get('to') != participant_id:
            return jsonify({'success': False, 'error': 'You are not the recipient of this offer'}), 403
        
        if offer.get('status') != 'pending':
            return jsonify({'success': False, 'error': 'Offer is no longer pending'}), 400
        
        # Find participants
        from_participant = None
        to_participant = None
        for p in participants_list:
            if p.get('id') == offer.get('from'):
                from_participant = p
            if p.get('id') == offer.get('to'):
                to_participant = p
        
        if not from_participant or not to_participant:
            return jsonify({'success': False, 'error': 'Participants not found'}), 404
        
        if response == 'accept':
            # Execute the trade - flexible item handling
            trade_item = offer.get('trade_item') or offer.get('shape')  # Backward compatible
            item_type = offer.get('item_type', 'shape')
            quantity = offer.get('quantity', 1)
            price = offer.get('price')
            offer_type = offer.get('offer_type')
            
            from_exp_params = from_participant.get('experiment_params', {})
            to_exp_params = to_participant.get('experiment_params', {})
            
            # Validate that seller has the item in inventory before executing trade
            if trade_item and item_type != 'price_only':
                seller_inventory = None
                seller_name = None
                
                if offer_type == 'sell':
                    # From is selling to To - check from_participant's inventory
                    seller_inventory = from_exp_params.get('inventory', [])
                    seller_name = from_participant.get('name', 'Seller')
                elif offer_type == 'buy':
                    # From is buying from To - To is selling, check to_participant's inventory
                    seller_inventory = to_exp_params.get('inventory', [])
                    seller_name = to_participant.get('name', 'Seller')
                
                if seller_inventory is not None:
                    # Check if item exists in seller's inventory
                    has_item = False
                    if isinstance(seller_inventory, list):
                        if item_type == 'shape':
                            # Count how many of this item are in inventory
                            item_count = seller_inventory.count(trade_item)
                            has_item = item_count >= quantity
                        else:
                            # For other types, check if enough items match
                            matching_items = [
                                item for item in seller_inventory
                                if (isinstance(item, dict) and item.get('type') == item_type and item.get('value') == trade_item) or
                                (not isinstance(item, dict) and item == trade_item)
                            ]
                            has_item = len(matching_items) >= quantity
                    
                    if not has_item:
                        item_display = trade_item if isinstance(trade_item, str) else str(trade_item)
                        return jsonify({
                            'success': False, 
                            'error': f'{seller_name} does not have {quantity}x {item_display} in inventory'
                        }), 400
            
            # Validate that buyer has enough money before executing trade
            buyer_money = None
            buyer_name = None
            
            if offer_type == 'sell':
                # From is selling to To - To is the buyer
                buyer_money = to_exp_params.get('money', 0)
                buyer_name = to_participant.get('name', 'Buyer')
            elif offer_type == 'buy':
                # From is buying from To - From is the buyer
                buyer_money = from_exp_params.get('money', 0)
                buyer_name = from_participant.get('name', 'Buyer')
            
            if buyer_money is not None and buyer_money < price:
                return jsonify({
                    'success': False,
                    'error': f'{buyer_name} does not have enough money (has ${buyer_money}, needs ${price})'
                }), 400
            
            # Helper function to remove item from inventory
            def remove_item_from_inventory(inventory, item, item_type, qty=1):
                if not isinstance(inventory, list):
                    return inventory
                new_inventory = inventory.copy()
                for _ in range(qty):
                    if item_type == 'shape':
                        if item in new_inventory:
                            new_inventory.remove(item)
                    else:
                        # For other types, find and remove matching item
                        for i, inv_item in enumerate(new_inventory):
                            if isinstance(inv_item, dict):
                                if inv_item.get('type') == item_type and inv_item.get('value') == item:
                                    new_inventory.pop(i)
                                    break
                            elif inv_item == item:
                                new_inventory.pop(i)
                                break
                return new_inventory
            
            # Helper function to add item to inventory
            def add_item_to_inventory(inventory, item, item_type, qty=1):
                if not isinstance(inventory, list):
                    inventory = []
                new_inventory = inventory.copy()
                for _ in range(qty):
                    if item_type == 'shape':
                        new_inventory.append(item)
                    else:
                        new_inventory.append({'type': item_type, 'value': item})
                return new_inventory
            
            if offer_type == 'sell':
                # From is selling to To
                if trade_item and item_type != 'price_only':
                    # Remove item from seller's inventory
                    from_inventory = from_exp_params.get('inventory', [])
                    from_exp_params['inventory'] = remove_item_from_inventory(from_inventory, trade_item, item_type, quantity)
                    
                    # Add item to buyer's inventory
                    to_inventory = to_exp_params.get('inventory', [])
                    to_exp_params['inventory'] = add_item_to_inventory(to_inventory, trade_item, item_type, quantity)
                
                # Add money to seller
                from_money = from_exp_params.get('money', 0)
                from_exp_params['money'] = from_money + price
                
                # Remove money from buyer
                to_money = to_exp_params.get('money', 0)
                to_exp_params['money'] = to_money - price
                
            elif offer_type == 'buy':
                # From is buying from To (To is selling)
                if trade_item and item_type != 'price_only':
                    # Remove item from seller's (To's) inventory
                    to_inventory = to_exp_params.get('inventory', [])
                    to_exp_params['inventory'] = remove_item_from_inventory(to_inventory, trade_item, item_type, quantity)
                    
                    # Add item to buyer's (From's) inventory
                    from_inventory = from_exp_params.get('inventory', [])
                    from_exp_params['inventory'] = add_item_to_inventory(from_inventory, trade_item, item_type, quantity)
                
                # Add money to seller (To)
                to_money = to_exp_params.get('money', 0)
                to_exp_params['money'] = to_money + price
                
                # Remove money from buyer (From)
                from_money = from_exp_params.get('money', 0)
                from_exp_params['money'] = from_money - price
            
            # Update participants
            from_participant['experiment_params'] = from_exp_params
            to_participant['experiment_params'] = to_exp_params
            
            # Recompute interfaces to ensure frontend gets updated data (especially money)
            update_participant_experiment_params(from_participant, found_session)
            update_participant_experiment_params(to_participant, found_session)
            
            # Create completed trade record
            if 'completed_trades' not in found_session:
                found_session['completed_trades'] = []
            
            completed_trade = {
                'id': str(uuid.uuid4()),
                'from': offer.get('from'),
                'to': offer.get('to'),
                'offer_type': offer_type,
                'item_type': item_type,
                'quantity': quantity,
                'price': price,
                'status': 'completed',
                'timestamp': datetime.now().isoformat()
            }
            # Add item data (backward compatible)
            if trade_item:
                completed_trade['trade_item'] = trade_item
                if item_type == 'shape':
                    completed_trade['shape'] = trade_item
            found_session['completed_trades'].append(completed_trade)
            
            # Remove from pending offers
            pending_offers.pop(offer_index)
            offer['status'] = 'accepted'
            
        else:  # decline
            # Create declined trade record
            if 'completed_trades' not in found_session:
                found_session['completed_trades'] = []
            
            declined_trade = {
                'id': str(uuid.uuid4()),
                'from': offer.get('from'),
                'to': offer.get('to'),
                'offer_type': offer.get('offer_type'),
                'item_type': offer.get('item_type', 'shape'),
                'quantity': offer.get('quantity', 1),
                'price': offer.get('price'),
                'status': 'declined',
                'timestamp': datetime.now().isoformat()
            }
            # Add item data (backward compatible)
            trade_item = offer.get('trade_item') or offer.get('shape')
            if trade_item:
                declined_trade['trade_item'] = trade_item
                if offer.get('item_type', 'shape') == 'shape':
                    declined_trade['shape'] = trade_item
            found_session['completed_trades'].append(declined_trade)
            
            # Remove from pending offers
            pending_offers.pop(offer_index)
            offer['status'] = 'declined'
        
        # Update session
        found_session['pending_offers'] = pending_offers
        found_session['participants'] = participants_list
        session_module.commit_session(session_key, found_session)
        
        # Broadcast update
        broadcast_participant_update(
            session_id=session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='trade_update'
        )
        
        # Action log (responder is participant_id)
        action_content = f"{response} offer from {offer.get('from')} (${offer.get('price')})"
        _log_human_action(
            session_key, found_session, participant_id, 'respond_to_offer',
            action_content, result='success',
            metadata={'offer_id': offer_id, 'response': response, 'from': offer.get('from')},
            data=data,
        )
        
        # In-session annotation: trigger on trade completion (accept) when annotation enabled
        if response == 'accept':
            try:
                from services.annotation_service import (
                    should_trigger_annotation,
                    trigger_annotation,
                )
                should_trigger, checkpoint = should_trigger_annotation(
                    session_key, found_session, participant_id, 'trade_completed'
                )
                if should_trigger and checkpoint is not None:
                    trigger_annotation(session_key, found_session, checkpoint, sessions)
            except Exception as ann_err:
                print(f'[Annotation] Error checking/triggering after trade: {ann_err}')
        
        return jsonify({
            'success': True,
            'response': response,
            'offer': offer
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Cancel trade offer
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/cancel_offer', methods=['POST'])
def cancel_offer(session_identifier, participant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        offer_id = data.get('offer_id')
        if not offer_id:
            return jsonify({'success': False, 'error': 'offer_id is required'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        participants_list = found_session.get('participants', [])
        pending_offers = found_session.get('pending_offers', [])
        
        # Find the offer
        offer = None
        offer_index = None
        for i, o in enumerate(pending_offers):
            if o.get('id') == offer_id:
                offer = o
                offer_index = i
                break
        
        if not offer:
            return jsonify({'success': False, 'error': 'Offer not found'}), 404
        
        # Verify participant is the sender
        if offer.get('from') != participant_id:
            return jsonify({'success': False, 'error': 'You are not the sender of this offer'}), 403
        
        if offer.get('status') != 'pending':
            return jsonify({'success': False, 'error': 'Offer is no longer pending'}), 400
        
        # Create cancelled trade record
        if 'completed_trades' not in found_session:
            found_session['completed_trades'] = []
        
        cancelled_trade = {
            'id': str(uuid.uuid4()),
            'from': offer.get('from'),
            'to': offer.get('to'),
            'offer_type': offer.get('offer_type'),
            'item_type': offer.get('item_type', 'shape'),
            'quantity': offer.get('quantity', 1),
            'price': offer.get('price'),
            'status': 'cancelled',
            'timestamp': datetime.now().isoformat()
        }
        # Add item data (backward compatible)
        trade_item = offer.get('trade_item') or offer.get('shape')
        if trade_item:
            cancelled_trade['trade_item'] = trade_item
            if offer.get('item_type', 'shape') == 'shape':
                cancelled_trade['shape'] = trade_item
        found_session['completed_trades'].append(cancelled_trade)
        
        # Remove from pending offers
        pending_offers.pop(offer_index)
        offer['status'] = 'cancelled'
        
        # Update session
        found_session['pending_offers'] = pending_offers
        session_module.commit_session(session_key, found_session)
        
        # Broadcast update
        broadcast_participant_update(
            session_id=session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='trade_update'
        )
        
        # Action log
        _log_human_action(
            session_key, found_session, participant_id, 'cancel_offer',
            f"Cancel offer to {offer.get('to')} (${offer.get('price')})",
            result='success', metadata={'offer_id': offer_id}, data=data,
        )
        
        return jsonify({
            'success': True,
            'offer': offer
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
# Submit essay ranking
@participant_bp.route('/api/sessions/<path:session_identifier>/participants/<participant_id>/submit_essay_rank', methods=['POST'])
def submit_essay_rank(session_identifier, participant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Find session
        session_key, found_session = find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Find participant
        participants_list = found_session.get('participants', [])
        participant = None
        for p in participants_list:
            if p.get('id') == participant_id:
                participant = p
                break
        
        if not participant:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
        
        # Get ranking data
        essay_id = data.get('essay_id')
        essay_rank = data.get('essay_rank')
        
        # Validate data
        if not essay_id:
            return jsonify({'success': False, 'error': 'essay_id is required'}), 400
        
        if essay_rank is None:
            return jsonify({'success': False, 'error': 'essay_rank is required'}), 400
        
        try:
            essay_rank = int(essay_rank)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'essay_rank must be a number'}), 400
        
        # Get participant's essays to validate essay_id
        exp_params = participant.get('experiment_params', {})
        essays = exp_params.get('essays', [])
        
        # Check if essay exists
        essay = next((e for e in essays if e.get('essay_id') == essay_id), None)
        if not essay:
            return jsonify({'success': False, 'error': f'Essay with id {essay_id} not found'}), 404
        
        # Initialize rankings if it doesn't exist
        if 'rankings' not in exp_params:
            exp_params['rankings'] = []
        
        # Ensure rankings is a list
        if not isinstance(exp_params['rankings'], list):
            exp_params['rankings'] = []
        
        # Check if ranking for this essay already exists, update it
        existing_ranking = next((r for r in exp_params['rankings'] if r.get('essay_id') == essay_id), None)
        
        if existing_ranking:
            # Update existing ranking
            existing_ranking['rank'] = essay_rank
            existing_ranking['updated_at'] = datetime.now().isoformat()
            # Ensure essay_title is set (in case it was missing)
            if 'essay_title' not in existing_ranking or not existing_ranking.get('essay_title'):
                existing_ranking['essay_title'] = essay.get('title') or essay.get('original_filename') or essay_id
            ranking_record = existing_ranking
        else:
            # Create new ranking record
            ranking_record = {
                'essay_id': essay_id,
                'essay_title': essay.get('title') or essay.get('original_filename') or essay_id,
                'rank': essay_rank,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            exp_params['rankings'].append(ranking_record)
        
        # Update participant
        participant['experiment_params'] = exp_params
        
        # Recompute interface to ensure frontend gets updated data
        update_participant_experiment_params(participant, found_session)
        
        # Update session (important: update the participant in the list)
        for i, p in enumerate(participants_list):
            if p.get('id') == participant_id:
                participants_list[i] = participant
                break
        
        found_session['participants'] = participants_list
        session_module.commit_session(session_key, found_session)
        
        # Log the update for debugging
        print(f'[submit_essay_rank] Updated participant {participant_id}:')
        print(f'  - Essay: {essay.get("title", essay_id)}')
        print(f'  - Rank: {essay_rank}')
        print(f'  - Total rankings: {len(exp_params["rankings"])}')
        
        # Broadcast update to all participants
        broadcast_participant_update(
            session_id=session_key,
            participants=participants_list,
            session_info=found_session,
            update_type='ranking_update'
        )
        
        return jsonify({
            'success': True,
            'ranking': ranking_record,
            'total_rankings': len(exp_params['rankings'])
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
