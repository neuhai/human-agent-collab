# REST API for sessions setting

from flask import request, jsonify, Blueprint
from datetime import datetime, timezone
import uuid
import os
import json
from werkzeug.utils import secure_filename
from config.experiments import get_experiment_by_id, EXPERIMENTS, PARTICIPANTS

try:
    import yaml
except Exception:
    yaml = None

# Create a blueprint for session routes
session_bp = Blueprint('session', __name__)


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Get all experiments (single source of truth for frontend)
@session_bp.route('/api/experiments', methods=['GET'])
def get_experiments():
    """Return experiment configs - frontend uses this for setup UI structure."""
    return jsonify(EXPERIMENTS), 200


@session_bp.route('/api/participants/templates', methods=['GET'])
def get_participant_templates():
    """Return participant templates keyed by experiment id."""
    return jsonify(_get_participant_templates_map()), 200


def _get_participant_templates_map():
    """
    PARTICIPANTS is stored as a one-item list containing {experiment_id: [template]}.
    Return a direct dict mapping experiment_id -> [template].
    """
    if not isinstance(PARTICIPANTS, list) or not PARTICIPANTS:
        return {}
    first = PARTICIPANTS[0]
    return first if isinstance(first, dict) else {}


def _extract_schema_keys(node, path=''):
    """
    Flatten all keys from a nested object into dotted paths.
    Used to compare uploaded config keys against backend canonical schema.
    """
    keys = set()
    if isinstance(node, dict):
        for k, v in node.items():
            key_path = f'{path}.{k}' if path else str(k)
            keys.add(key_path)
            keys.update(_extract_schema_keys(v, key_path))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            list_path = f'{path}[{idx}]'
            keys.add(list_path)
            keys.update(_extract_schema_keys(item, list_path))
    return keys


def _try_parse_uploaded_config(content_text, file_name):
    ext = os.path.splitext(file_name or '')[1].lower()
    parse_errors = []

    # Try JSON first (many users upload json even with non-json extension)
    try:
        return json.loads(content_text), None
    except Exception as e:
        parse_errors.append(f'JSON parse failed: {e}')

    # Fallback to YAML when available
    if ext in ['.yaml', '.yml'] and yaml is not None:
        try:
            return yaml.safe_load(content_text), None
        except Exception as e:
            parse_errors.append(f'YAML parse failed: {e}')

    if ext in ['.yaml', '.yml'] and yaml is None:
        parse_errors.append('YAML parser not installed on server (PyYAML missing)')

    return None, '; '.join(parse_errors)


def _build_validation_result(uploaded_config):
    errors = []
    warnings = []

    if not isinstance(uploaded_config, dict):
        errors.append({
            'path': 'root',
            'message': 'Config root must be an object/dictionary.'
        })
        return {
            'valid': False,
            'errors': errors,
            'warnings': warnings,
            'normalized_config': None
        }

    # Supported upload structure:
    # {
    #   "experiment": {...},
    #   "participant": {...} | "participants": {...}
    # }
    experiment = uploaded_config.get('experiment')
    participant = uploaded_config.get('participant', uploaded_config.get('participants'))

    if experiment is None:
        errors.append({
            'path': 'experiment',
            'message': 'Missing required key: experiment'
        })
    if participant is None:
        errors.append({
            'path': 'participant',
            'message': 'Missing required key: participant (or participants)'
        })
    if errors:
        return {
            'valid': False,
            'errors': errors,
            'warnings': warnings,
            'normalized_config': None
        }

    if not isinstance(experiment, dict):
        errors.append({
            'path': 'experiment',
            'message': 'experiment must be an object.'
        })
        return {
            'valid': False,
            'errors': errors,
            'warnings': warnings,
            'normalized_config': None
        }
    if not isinstance(participant, dict):
        errors.append({
            'path': 'participant',
            'message': 'participant must be an object keyed by experiment id.'
        })
        return {
            'valid': False,
            'errors': errors,
            'warnings': warnings,
            'normalized_config': None
        }

    exp_id = experiment.get('id')
    if not exp_id:
        errors.append({
            'path': 'experiment.id',
            'message': 'experiment.id is required.'
        })
        return {
            'valid': False,
            'errors': errors,
            'warnings': warnings,
            'normalized_config': None
        }

    canonical_experiment = get_experiment_by_id(exp_id)
    canonical_participants = _get_participant_templates_map()
    canonical_participant_template = canonical_participants.get(exp_id)

    if not canonical_experiment:
        errors.append({
            'path': 'experiment.id',
            'message': f'Unknown experiment id: {exp_id}'
        })
    if canonical_participant_template is None:
        errors.append({
            'path': f'participant.{exp_id}',
            'message': f'No canonical participant template found for experiment id: {exp_id}'
        })
    if errors:
        return {
            'valid': False,
            'errors': errors,
            'warnings': warnings,
            'normalized_config': None
        }

    participant_for_exp = participant.get(exp_id)
    if participant_for_exp is None:
        errors.append({
            'path': f'participant.{exp_id}',
            'message': f'participant must include key "{exp_id}" to match experiment.id.'
        })
        return {
            'valid': False,
            'errors': errors,
            'warnings': warnings,
            'normalized_config': None
        }

    # Validate required high-level keys from canonical experiment
    required_experiment_keys = ['id', 'name', 'params', 'interaction', 'participant_settings', 'interface']
    for key in required_experiment_keys:
        if key not in experiment:
            errors.append({
                'path': f'experiment.{key}',
                'message': f'Missing required key: experiment.{key}'
            })

    # Schema compatibility check (key-level): detect unknown keys and missing canonical keys
    canonical_exp_keys = _extract_schema_keys(canonical_experiment)
    uploaded_exp_keys = _extract_schema_keys(experiment)
    missing_exp_keys = sorted(k for k in canonical_exp_keys if k not in uploaded_exp_keys)
    unknown_exp_keys = sorted(k for k in uploaded_exp_keys if k not in canonical_exp_keys)

    for k in missing_exp_keys[:30]:
        errors.append({
            'path': f'experiment.{k}',
            'message': 'Missing key compared with backend canonical experiment config.'
        })
    if len(missing_exp_keys) > 30:
        warnings.append(f'{len(missing_exp_keys) - 30} additional missing experiment keys omitted.')

    for k in unknown_exp_keys[:30]:
        warnings.append(f'Unknown experiment key (not in canonical schema): {k}')
    if len(unknown_exp_keys) > 30:
        warnings.append(f'{len(unknown_exp_keys) - 30} additional unknown experiment keys omitted.')

    # Participant schema check (for the selected experiment)
    canonical_participant_keys = _extract_schema_keys(canonical_participant_template)
    uploaded_participant_keys = _extract_schema_keys(participant_for_exp)
    missing_participant_keys = sorted(k for k in canonical_participant_keys if k not in uploaded_participant_keys)
    unknown_participant_keys = sorted(k for k in uploaded_participant_keys if k not in canonical_participant_keys)

    for k in missing_participant_keys[:30]:
        errors.append({
            'path': f'participant.{exp_id}.{k}',
            'message': 'Missing key compared with backend canonical participant template.'
        })
    if len(missing_participant_keys) > 30:
        warnings.append(f'{len(missing_participant_keys) - 30} additional missing participant keys omitted.')

    for k in unknown_participant_keys[:30]:
        warnings.append(f'Unknown participant key (not in canonical schema): {k}')
    if len(unknown_participant_keys) > 30:
        warnings.append(f'{len(unknown_participant_keys) - 30} additional unknown participant keys omitted.')

    valid = len(errors) == 0

    # "Auto-fix": when valid, normalize to canonical skeleton + user provided values
    # (deep merge semantics are intentionally simple for now)
    normalized = {
        'experiment': experiment,
        'participant': {
            exp_id: participant_for_exp
        }
    } if valid else None

    return {
        'valid': valid,
        'errors': errors,
        'warnings': warnings,
        'normalized_config': normalized
    }


@session_bp.route('/api/experiments/validate-upload', methods=['POST'])
def validate_uploaded_experiment_config():
    """
    Validate uploaded custom experiment config against backend canonical config.
    Request JSON:
      {
        "fileName": "...",
        "content": "raw file text"
      }
    """
    try:
        data = request.get_json() or {}
        file_name = data.get('fileName', '')
        content = data.get('content', '')

        if not content or not isinstance(content, str):
            return jsonify({
                'valid': False,
                'errors': [{'path': 'content', 'message': 'content is required and must be a string.'}],
                'warnings': []
            }), 400

        parsed, parse_error = _try_parse_uploaded_config(content, file_name)
        if parse_error:
            return jsonify({
                'valid': False,
                'errors': [{'path': 'file', 'message': parse_error}],
                'warnings': []
            }), 400

        result = _build_validation_result(parsed)
        status = 200 if result.get('valid') else 422
        return jsonify(result), status
    except Exception as e:
        return jsonify({
            'valid': False,
            'errors': [{'path': 'server', 'message': str(e)}],
            'warnings': []
        }), 500

# In-memory storage for sessions (also persisted to PostgreSQL when configured)
sessions = {}


def commit_session(session_key: str, session_dict: dict) -> None:
    """Store session in memory and upsert to database (full JSON snapshot)."""
    sessions[session_key] = session_dict
    try:
        from services.db import persist_research_session

        persist_research_session(session_dict)
    except Exception as e:
        print(f'[Session] DB persist: {e}')


def set_session_started_at_when_timer_starts(session_timer_id: str, iso_z: str) -> None:
    """
    Set session started_at to the instant the countdown first begins (TimerService internal start).
    Keeps post-hoc timelines and Session.Params.duration aligned with the participant-visible timer
    when /start used delay_timer (popups / reading window before the clock runs).
    """
    for session_key, sess in sessions.items():
        cand = sess.get('session_id') or session_key
        if cand != session_timer_id:
            continue
        cur = sess.get('started_at')
        if cur is None or (isinstance(cur, str) and not str(cur).strip()):
            sess['started_at'] = iso_z
            commit_session(session_key, sess)
            print(f'[Session] started_at aligned to timer start for {session_timer_id}')
        return


def hydrate_sessions_from_db() -> None:
    """Load saved sessions into memory on startup."""
    try:
        from services.db import is_db_configured, load_all_research_sessions

        if not is_db_configured():
            return
        loaded = load_all_research_sessions()
        for sid, s in loaded.items():
            sessions[sid] = s
        if loaded:
            print(f'[Session] Loaded {len(loaded)} session(s) from database')
    except Exception as e:
        print(f'[Session] hydrate from DB failed: {e}')

# Create a new session
@session_bp.route('/api/sessions', methods=['POST'])
def create_session():
    try:
        data = request.get_json()
        
        # Validate request data
        if not data or 'sessionName' not in data:
            return jsonify({'error': 'sessionName is required'}), 400
        
        session_name = data['sessionName'].strip()
        if not session_name:
            return jsonify({'error': 'sessionName cannot be empty'}), 400
        
        # Check if session name already exists (case-insensitive)
        for session_id, session in sessions.items():
            if session.get('session_name', '').lower() == session_name.lower():
                return jsonify({
                    'error': 'Session name already exists. Please use a different name or load the existing session.',
                    'code': 'SESSION_EXISTS'
                }), 409
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Create session object
        session = {
            'session_id': session_id,
            'session_name': session_name,
            'experiment_type': None,
            'status': 'waiting',
            'config': {},
            'params': {},
            'interaction': {},
            'created_at': _utc_now_iso_z(),
            'started_at': None,
            'duration_minutes': None,
            'remaining_seconds': None,
            'participants': [],
            'pending_offers': [],
            'completed_trades': []
        }
        
        # Store session
        commit_session(session_id, session)

        # Return session ID as JSON object for better compatibility
        return jsonify({'session_id': session_id}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Get session info by session_id (UUID) or session name
@session_bp.route('/api/sessions/<path:session_identifier>', methods=['GET'])
def get_session(session_identifier):
    try:
        # URL decode in case it contains special characters
        from urllib.parse import unquote
        session_identifier = unquote(session_identifier)
        
        found_session = None
        # First try direct lookup by session_id (UUID)
        if session_identifier in sessions:
            found_session = sessions[session_identifier]
        else:
            # Search for session by name (case-insensitive search)
            for sid, session in sessions.items():
                if session.get('session_name', '').lower() == session_identifier.lower():
                    found_session = session
                    break
        
        if not found_session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Return session info with 'id' field for frontend compatibility
        session_response = found_session.copy()
        session_response['id'] = found_session['session_id']
        
        return jsonify(session_response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Update session info (supports updating by session_id or session_name)
@session_bp.route('/api/sessions/<path:session_identifier>', methods=['PUT'])
def update_session(session_identifier):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Find session by ID or name
        from urllib.parse import unquote
        session_identifier = unquote(session_identifier)
        
        found_session = None
        session_key = None
        
        # Try to find by session_id first (UUID format)
        if session_identifier in sessions:
            found_session = sessions[session_identifier]
            session_key = session_identifier
        else:
            # Try to find by session_name (case-insensitive)
            for sid, session in sessions.items():
                if session.get('session_name', '').lower() == session_identifier.lower():
                    found_session = session
                    session_key = sid
                    break
        
        if not found_session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Update allowed fields
        allowed_fields = [
            'experiment_type',
            'status',
            'config',
            'params',
            'interaction',
            'duration_minutes',
            'remaining_seconds',
            'session_name',
            'experiment_config'
        ]
        
        # Update fields from request data
        updated = False
        experiment_type_updated = False
        ui_related_changed = False
        status_changed_to_running = False
        
        for key, value in data.items():
            if key in allowed_fields:
                # If experiment_type is being updated, mark it for special handling
                if key == 'experiment_type':
                    experiment_type_updated = True
                # 标记与 UI / interface 相关的字段是否被修改
                if key in ('experiment_type', 'config', 'params', 'interaction', 'experiment_config'):
                    ui_related_changed = True
                # Check if status is being changed to 'running'
                if key == 'status' and value == 'running' and found_session.get('status') != 'running':
                    status_changed_to_running = True
                
                # For experiment_config, merge with existing config to preserve other settings
                if key == 'experiment_config' and isinstance(value, dict):
                    existing_config = found_session.get('experiment_config', {})
                    found_session[key] = {**existing_config, **value}
                else:
                    found_session[key] = value
                updated = True
        
        # If experiment_type was updated, automatically update all experiment config fields
        if experiment_type_updated and found_session.get('experiment_type'):
            experiment_id = found_session['experiment_type']
            experiment_config = get_experiment_by_id(experiment_id)
            
            if experiment_config:
                # Update all fields from experiment config
                # Store the full experiment config for reference
                found_session['experiment_config'] = experiment_config
                
                # Update params if experiment has params
                if 'params' in experiment_config and experiment_config['params']:
                    found_session['params'] = experiment_config['params']
                
                # Update interaction if experiment has interaction
                if 'interaction' in experiment_config and experiment_config['interaction']:
                    found_session['interaction'] = experiment_config['interaction']
            
            # Register agent runners for any AI participants now that experiment_type is set
            try:
                from agent.agent_runner import register_agent_runner
                from websocket.handlers import broadcast_participant_update
                participants = found_session.get('participants', [])
                session_id = found_session.get('session_id') or session_key
                
                updated_participants = []
                agents_registered = False
                for participant in participants:
                    participant_type = participant.get('type', '').lower()
                    if participant_type in ['ai', 'ai_agent']:
                        participant_role = participant.get('role')  # For wordguessing
                        register_agent_runner(
                            participant_id=participant.get('id'),
                            session_id=session_id,
                            experiment_type=experiment_id,
                            participant_role=participant_role
                        )
                        # Mark agent as online
                        participant['status'] = 'online'
                        agents_registered = True
                        participant_name = participant.get('name') or participant.get('participant_name')
                        print(f'[Session] Registered agent runner for participant {participant.get("id")} ({participant_name}) after experiment_type update, marked as online')
                        updated_participants.append(participant)
                    else:
                        updated_participants.append(participant)
                
                # Update participants list and broadcast if any agents were registered
                if agents_registered:
                    found_session['participants'] = updated_participants
                    commit_session(session_key, found_session)
                    broadcast_participant_update(
                        session_id=session_id,
                        participants=updated_participants,
                        session_info=found_session,
                        update_type='partial'
                    )
                    print(f'[Session] Broadcasted online status update for {len([p for p in updated_participants if p.get("type", "").lower() in ["ai", "ai_agent"]])} AI participants')
            except Exception as e:
                print(f'[Session] Error registering agent runners after experiment_type update: {e}')
                import traceback
                traceback.print_exc()
        
        # 如果这次请求修改了会影响前端 UI 的字段，则重算所有 participant 的 interface
        updated_participants = None
        if ui_related_changed:
            try:
                # 懒加载，避免循环依赖
                from routes.participant import update_participant_experiment_params
                participants = found_session.get('participants', [])
                updated_participants = []
                for p in participants:
                    updated_participants.append(update_participant_experiment_params(p, found_session))
                found_session['participants'] = updated_participants
            except Exception as e:
                # 不要因为这里失败而让整个 session 更新失败，先打印错误
                print(f'Error updating participants after session config change: {e}')
        
        if not updated:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        # If status changed to 'running', start all agent runners
        if status_changed_to_running:
            try:
                from agent.agent_runner import start_agent_runner, get_agent_runner
                participants = found_session.get('participants', [])
                session_id = found_session.get('session_id') or session_key
                experiment_type = found_session.get('experiment_type')
                
                # Check if there are any human participants
                has_human_participant = any(
                    p.get('type', '').lower() not in ['ai', 'ai_agent'] 
                    for p in participants
                )
                
                # Collect all agent participant IDs first
                agent_participant_ids = []
                for participant in participants:
                    participant_type = participant.get('type', '').lower()
                    if participant_type in ['ai', 'ai_agent']:
                        start_agent_runner(
                            participant_id=participant.get('id'),
                            session_id=session_id
                        )
                        print(f'[Session] Started agent runner for participant {participant.get("id")} in session {session_id}')
                        agent_participant_ids.append(participant.get('id'))
                
                # For hiddenprofile experiment, trigger initial vote for all agents
                # If no human participants, trigger immediately
                # If there are human participants, check if initial vote popup should be shown
                if experiment_type == 'hiddenprofile' and agent_participant_ids:
                    import threading
                    import time
                    
                    def trigger_initial_vote_for_agent(agent_participant_id):
                        # Wait longer to ensure agent runner is fully initialized and started
                        time.sleep(5)  # Wait 5 seconds for agent runner to fully initialize
                        # Re-fetch session and participant to get latest state
                        from routes.participant import find_session_by_identifier
                        session_key_latest, session_latest = find_session_by_identifier(session_id)
                        if not session_latest:
                            return
                        
                        # Find participant in latest session
                        participant_latest = None
                        for p in session_latest.get('participants', []):
                            if p.get('id') == agent_participant_id:
                                participant_latest = p
                                break
                        
                        if not participant_latest:
                            return
                        
                        runner = get_agent_runner(agent_participant_id, session_id)
                        if runner:
                            result = runner._trigger_vote('initial', participant_latest, session_latest, session_key_latest)
                        else:
                            # Try to import _agent_runners for debugging
                            try:
                                from agent.agent_runner import _agent_runners
                            except:
                                pass
                    
                    # If no human participants, trigger vote immediately
                    if not has_human_participant:
                        # Trigger vote for each agent in separate thread
                        for agent_id in agent_participant_ids:
                            threading.Thread(target=trigger_initial_vote_for_agent, args=(agent_id,), daemon=True).start()
                    else:
                        # If there are human participants, check if any human has shown initial vote popup
                        # We check by looking for human participants with initial_vote still 'none' or not set
                        # If session is running, it means initial vote popup might have been shown
                        # We'll trigger agents when human shows the popup (via WebSocket event)
                        # But also check if any human participant already has initial_vote set (meaning popup was shown earlier)
                        human_with_vote_popup_shown = False
                        for participant in participants:
                            participant_type = participant.get('type', '').lower()
                            if participant_type not in ['ai', 'ai_agent']:
                                # Check if this human participant has initial vote popup shown
                                # If initial_vote is 'none' or not set, popup might be shown
                                initial_vote = participant.get('experiment_params', {}).get('initial_vote')
                                # If initial_vote is None or 'none', the popup should be shown
                                if initial_vote is None or initial_vote == 'none':
                                    human_with_vote_popup_shown = True
                                    break
                        
                        # If we detect that initial vote popup should be shown, trigger agents
                        # This handles the case where session starts and popup is already shown
                        if human_with_vote_popup_shown:
                            print(f'[Session] HiddenProfile: Human participant detected with initial vote popup, triggering {len(agent_participant_ids)} AI agents')
                            # Use WebSocket handler logic to trigger agents (simulate vote_popup_shown event)
                            # We'll trigger via the same mechanism as WebSocket handler
                            for agent_id in agent_participant_ids:
                                threading.Thread(target=trigger_initial_vote_for_agent, args=(agent_id,), daemon=True).start()
            except Exception as e:
                print(f'[Session] Error starting agent runners: {e}')
                import traceback
                traceback.print_exc()
        
        # Update the session in storage
        commit_session(session_key, found_session)

        # 如果刚刚重算了 participants，则通过 websocket 广播给该 session 的所有客户端
        # Also broadcast if interaction was updated (even if participants weren't recalculated)
        should_broadcast = updated_participants is not None or ui_related_changed
        if should_broadcast:
            try:
                from websocket.handlers import broadcast_participant_update
                # Use session_id from found_session, not session_key (which might be session_name)
                broadcast_session_id = found_session.get('session_id') or session_key
                # Use updated participants if available, otherwise use current participants
                participants_to_broadcast = updated_participants if updated_participants is not None else found_session.get('participants', [])
                broadcast_participant_update(
                    session_id=broadcast_session_id,
                    participants=participants_to_broadcast,
                    session_info=found_session,
                    update_type='config_changed'
                )
                print(f'[Session] Broadcasted session update (interaction/config changed)')
            except Exception as e:
                print(f'Error broadcasting participant update after session config change: {e}')
                import traceback
                traceback.print_exc()
        
        # Return updated session info with 'id' field for frontend compatibility
        session_response = found_session.copy()
        session_response['id'] = found_session['session_id']
        
        return jsonify(session_response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Delete session
@session_bp.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    try:
        # Find session by ID or name
        from urllib.parse import unquote
        session_identifier = unquote(session_id)
        
        found_session = None
        session_key = None
        
        # Try to find by session_id first (UUID format)
        if session_identifier in sessions:
            found_session = sessions[session_identifier]
            session_key = session_identifier
        else:
            # Try to find by session_name (case-insensitive)
            for sid, session in sessions.items():
                if session.get('session_name', '').lower() == session_identifier.lower():
                    found_session = session
                    session_key = sid
                    break
        
        if not found_session:
            return jsonify({'error': 'Session not found'}), 404

        try:
            from services.db import delete_research_session

            delete_research_session(found_session.get('session_id') or session_key)
        except Exception as e:
            print(f'[Session] DB delete: {e}')

        # Delete session
        del sessions[session_key]

        return jsonify({'message': 'Session deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper function to update session status and broadcast
def update_session_status(session_identifier, new_status, started_at=None, remaining_seconds=None):
    """Update session status and broadcast to all participants via WebSocket"""
    try:
        from urllib.parse import unquote
        session_identifier = unquote(session_identifier)
        
        found_session = None
        session_key = None
        
        # Try to find by session_id first (UUID format)
        if session_identifier in sessions:
            found_session = sessions[session_identifier]
            session_key = session_identifier
        else:
            # Try to find by session_name (case-insensitive)
            for sid, session in sessions.items():
                if session.get('session_name', '').lower() == session_identifier.lower():
                    found_session = session
                    session_key = sid
                    break
        
        if not found_session:
            return None, None, jsonify({'error': 'Session not found'}), 404
        
        # Update status
        old_status = found_session.get('status')
        found_session['status'] = new_status
        
        # Update started_at if provided
        if started_at is not None:
            found_session['started_at'] = started_at
        
        # Update remaining_seconds if provided
        if remaining_seconds is not None:
            found_session['remaining_seconds'] = remaining_seconds
        
        # Save session
        commit_session(session_key, found_session)
        
        # Start/stop agent runners based on status FIRST (before broadcasting)
        # This ensures online status is updated before we broadcast
        # Note: Agent runners check session status in their perception loop,
        # so they automatically pause when status is not 'running'
        try:
            from agent.agent_runner import start_agent_runner, stop_agent_runner
            participants_list = found_session.get('participants', [])
            session_id_for_agents = found_session.get('session_id') or session_key
            
            for participant in participants_list:
                participant_type = participant.get('type', '').lower()
                if participant_type in ['ai', 'ai_agent']:
                    participant_id = participant.get('id')
                    if new_status == 'running' and old_status != 'running':
                        # Start agent runner (this will update online status and broadcast)
                        start_agent_runner(participant_id=participant_id, session_id=session_id_for_agents)
                        print(f'[Session] Started agent runner for participant {participant_id}')
                    elif new_status == 'waiting' and old_status in ['running', 'paused']:
                        # Stop agent runner when resetting to waiting (this will update online status and broadcast)
                        stop_agent_runner(participant_id=participant_id, session_id=session_id_for_agents)
                        print(f'[Session] Stopped agent runner for participant {participant_id}')
                    # For pause/resume, agent runners automatically check session status
                    # so no explicit pause/resume needed, but we should still update online status
                    elif new_status == 'paused' and old_status == 'running':
                        # Mark as offline when paused (agent runner will pause automatically)
                        participant['status'] = 'offline'
                        commit_session(session_key, found_session)
                    elif new_status == 'running' and old_status == 'paused':
                        # Mark as online when resuming (agent runner will resume automatically)
                        participant['status'] = 'online'
                        commit_session(session_key, found_session)
            
            # Re-fetch participants list after agent runner updates
            found_session = sessions[session_key]
            participants_list = found_session.get('participants', [])
        except Exception as e:
            print(f'[Session] Error managing agent runners: {e}')
            import traceback
            traceback.print_exc()
        
        # Broadcast status update via WebSocket (after online status is updated)
        try:
            from websocket.handlers import broadcast_participant_update
            session_id_for_broadcast = found_session.get('session_id') or session_key
            
            broadcast_participant_update(
                session_id=session_id_for_broadcast,
                participants=participants_list,
                session_info=found_session,
                update_type='status_changed'
            )
            print(f'[Session] Broadcasted status change: {old_status} -> {new_status} for session {session_id_for_broadcast}')
        except Exception as e:
            print(f'[Session] Error broadcasting status update: {e}')
        
        return found_session, session_key, None, None
        
    except Exception as e:
        return None, None, jsonify({'error': str(e)}), 500

# Start session
@session_bp.route('/api/sessions/<path:session_identifier>/start', methods=['POST'])
def start_session(session_identifier):
    try:
        # Check if delay_timer is requested (for auto start with popups)
        # Use silent=True to avoid errors when no JSON body is provided
        data = request.get_json(silent=True) or {}
        delay_timer = data.get('delay_timer', False)
        
        # First, find the session to check if it has started_at
        from urllib.parse import unquote
        session_id = unquote(session_identifier)
        
        found_before = None
        session_key_before = None
        
        if session_id in sessions:
            found_before = sessions[session_id]
            session_key_before = session_id
        else:
            for sid, session in sessions.items():
                if session.get('session_name', '').lower() == session_id.lower():
                    found_before = session
                    session_key_before = sid
                    break
        
        # started_at must match when the countdown actually runs (see TimerService.start +
        # set_session_started_at_when_timer_starts). Do not set it here on first run — avoids
        # skew when delay_timer is True (session is running before the clock starts).
        started_at_value = None
        if found_before and found_before.get('started_at'):
            started_at_value = found_before.get('started_at')

        # Update status
        found_session, session_key, error_response, error_code = update_session_status(
            session_identifier,
            'running',
            started_at=started_at_value,
        )
        
        if error_response:
            return error_response, error_code
        
        # Get duration from Session.Params.duration
        from routes.participant import get_value_from_session_params
        duration_minutes = get_value_from_session_params(found_session, 'Session.Params.duration')
        
        # Fallback to duration_minutes field if not found in params
        if duration_minutes is None:
            duration_minutes = found_session.get('duration_minutes')
        
        # Default to 30 minutes if not specified
        if duration_minutes is None:
            duration_minutes = 30
        
        duration_seconds = int(duration_minutes) * 60
        
        # Initialize or update remaining_seconds
        if not found_session.get('remaining_seconds') or found_session.get('status') == 'waiting':
            found_session['remaining_seconds'] = duration_seconds
            found_session['duration_minutes'] = duration_minutes
        
        commit_session(session_key, found_session)
        
        # Start timer service (unless delay_timer is True)
        if not delay_timer:
            try:
                from services.timer_service import create_timer, start_timer, get_timer
                session_id_for_timer = found_session.get('session_id') or session_key
                
                # Create timer if it doesn't exist
                timer = get_timer(session_id_for_timer)
                if not timer:
                    timer = create_timer(session_id_for_timer, duration_seconds)
                    timer.start()
                else:
                    # If timer exists, check if we're resuming from pause
                    if found_before and found_before.get('status') == 'paused':
                        timer.resume()
                    elif not timer.is_running:
                        timer.start()
                
                print(f'[Session] Started timer for session {session_id_for_timer}, duration: {duration_minutes} minutes')
            except Exception as e:
                print(f'[Session] Error starting timer: {e}')
                import traceback
                traceback.print_exc()
        else:
            # Create timer but don't start it yet
            try:
                from services.timer_service import create_timer, get_timer
                session_id_for_timer = found_session.get('session_id') or session_key
                
                timer = get_timer(session_id_for_timer)
                if not timer:
                    timer = create_timer(session_id_for_timer, duration_seconds)
                    # Don't start timer - it will be started later after popups complete
                    print(f'[Session] Created timer for session {session_id_for_timer} (delayed start), duration: {duration_minutes} minutes')
            except Exception as e:
                print(f'[Session] Error creating timer: {e}')
                import traceback
                traceback.print_exc()
        
        session_response = found_session.copy()
        session_response['id'] = found_session['session_id']
        
        return jsonify(session_response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Pause session
@session_bp.route('/api/sessions/<path:session_identifier>/pause', methods=['POST'])
def pause_session(session_identifier):
    try:
        found_session, session_key, error_response, error_code = update_session_status(
            session_identifier, 
            'paused'
        )
        
        if error_response:
            return error_response, error_code
        
        # Pause timer
        try:
            from services.timer_service import pause_timer
            session_id_for_timer = found_session.get('session_id') or session_key
            pause_timer(session_id_for_timer)
            print(f'[Session] Paused timer for session {session_id_for_timer}')
        except Exception as e:
            print(f'[Session] Error pausing timer: {e}')
        
        session_response = found_session.copy()
        session_response['id'] = found_session['session_id']
        
        return jsonify(session_response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Resume session
@session_bp.route('/api/sessions/<path:session_identifier>/resume', methods=['POST'])
def resume_session(session_identifier):
    try:
        found_session, session_key, error_response, error_code = update_session_status(
            session_identifier, 
            'running'
        )
        
        if error_response:
            return error_response, error_code
        
        # Resume timer
        try:
            from services.timer_service import resume_timer, get_timer
            session_id_for_timer = found_session.get('session_id') or session_key
            timer = get_timer(session_id_for_timer)
            if timer:
                timer.resume()
                print(f'[Session] Resumed timer for session {session_id_for_timer}')
            else:
                # If timer doesn't exist, start it
                from services.timer_service import create_timer
                from routes.participant import get_value_from_session_params
                duration_minutes = get_value_from_session_params(found_session, 'Session.Params.duration')
                if duration_minutes is None:
                    duration_minutes = found_session.get('duration_minutes', 30)
                duration_seconds = int(duration_minutes) * 60
                timer = create_timer(session_id_for_timer, duration_seconds)
                timer.start()
                print(f'[Session] Created and started timer for session {session_id_for_timer}')
        except Exception as e:
            print(f'[Session] Error resuming timer: {e}')
        
        session_response = found_session.copy()
        session_response['id'] = found_session['session_id']
        
        return jsonify(session_response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Reset session
@session_bp.route('/api/sessions/<path:session_identifier>/reset', methods=['POST'])
def reset_session(session_identifier):
    try:
        from urllib.parse import unquote
        session_identifier = unquote(session_identifier)
        
        found_session = None
        session_key = None
        
        # Try to find by session_id first (UUID format)
        if session_identifier in sessions:
            found_session = sessions[session_identifier]
            session_key = session_identifier
        else:
            # Try to find by session_name (case-insensitive)
            for sid, session in sessions.items():
                if session.get('session_name', '').lower() == session_identifier.lower():
                    found_session = session
                    session_key = sid
                    break
        
        if not found_session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Reset status to waiting
        found_session, session_key, error_response, error_code = update_session_status(
            session_identifier, 
            'waiting'
        )
        
        if error_response:
            return error_response, error_code
        
        # Reset timer and started_at
        found_session['started_at'] = None
        
        # Reset timer service
        try:
            from services.timer_service import reset_timer, stop_timer
            from routes.participant import get_value_from_session_params
            session_id_for_timer = found_session.get('session_id') or session_key
            
            # Get duration from Session.Params.duration
            duration_minutes = get_value_from_session_params(found_session, 'Session.Params.duration')
            if duration_minutes is None:
                duration_minutes = found_session.get('duration_minutes', 30)
            
            duration_seconds = int(duration_minutes) * 60
            found_session['remaining_seconds'] = duration_seconds
            found_session['duration_minutes'] = duration_minutes
            
            # Reset timer
            reset_timer(session_id_for_timer, duration_seconds)
            print(f'[Session] Reset timer for session {session_id_for_timer}')
        except Exception as e:
            print(f'[Session] Error resetting timer: {e}')
            # Fallback: set remaining_seconds to None
            found_session['remaining_seconds'] = None
        
        # Reset participants' experiment_params to initial state
        try:
            from routes.participant import update_participant_experiment_params
            participants = found_session.get('participants', [])
            for participant in participants:
                # Clear experiment_params to force re-initialization
                if 'experiment_params' in participant:
                    # Preserve participant ID and basic info, but reset experiment_params
                    participant['experiment_params'] = {}
                # Re-initialize from session params
                update_participant_experiment_params(participant, found_session)
            found_session['participants'] = participants
        except Exception as e:
            print(f'[Session] Error resetting participants: {e}')
        
        commit_session(session_key, found_session)
        
        # Broadcast update
        try:
            from websocket.handlers import broadcast_participant_update
            session_id_for_broadcast = found_session.get('session_id') or session_key
            broadcast_participant_update(
                session_id=session_id_for_broadcast,
                participants=found_session.get('participants', []),
                session_info=found_session,
                update_type='status_changed'
            )
        except Exception as e:
            print(f'[Session] Error broadcasting reset update: {e}')
        
        session_response = found_session.copy()
        session_response['id'] = found_session['session_id']
        
        return jsonify(session_response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Upload essay files
@session_bp.route('/api/sessions/<path:session_identifier>/upload_essays', methods=['POST'])
def upload_essays(session_identifier):
    try:
        from urllib.parse import unquote
        session_identifier = unquote(session_identifier)
        
        # Find session
        found_session = None
        session_key = None
        
        if session_identifier in sessions:
            found_session = sessions[session_identifier]
            session_key = session_identifier
        else:
            for sid, session in sessions.items():
                if session.get('session_name', '').lower() == session_identifier.lower():
                    found_session = session
                    session_key = sid
                    break
        
        if not found_session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Check if files are in request
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400
        
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'essays')
        os.makedirs(upload_dir, exist_ok=True)
        
        uploaded_essays = []
        session_essays = found_session.get('essays', [])
        
        for file in files:
            if file.filename == '':
                continue
            
            # Check if file is PDF
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({'error': f'Only PDF files are allowed. Received: {file.filename}'}), 400
            
            # Save original filename before secure_filename processing
            original_filename = file.filename
            # Generate unique filename for storage (use secure_filename for filesystem safety)
            safe_filename = secure_filename(original_filename)
            essay_id = str(uuid.uuid4())
            file_extension = os.path.splitext(safe_filename)[1] or '.pdf'
            unique_filename = f"{essay_id}{file_extension}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            # Save file
            file.save(file_path)
            
            # Extract title from original filename (preserve original encoding)
            title = os.path.splitext(original_filename)[0]
            
            # Create essay object
            essay_obj = {
                'essay_id': essay_id,
                'title': title,  # Use original filename for title
                'filename': unique_filename,
                'original_filename': original_filename,  # Preserve original filename
                'file_path': f'/api/essays/{unique_filename}',
                'uploaded_at': _utc_now_iso_z()
            }
            
            uploaded_essays.append(essay_obj)
            session_essays.append(essay_obj)
        
        # Update session with essays
        found_session['essays'] = session_essays
        
        # Sync essays to all participants
        participants = found_session.get('participants', [])
        updated_participants = []
        for participant in participants:
            exp_params = participant.get('experiment_params', {})
            if 'essays' not in exp_params:
                exp_params['essays'] = []
            
            # Add new essays to participant's essay list
            for essay in uploaded_essays:
                # Check if essay already exists (by essay_id)
                if not any(e.get('essay_id') == essay['essay_id'] for e in exp_params['essays']):
                    exp_params['essays'].append(essay)
            
            participant['experiment_params'] = exp_params
            print(f'[Session] Updated participant {participant.get("id")} essays: {len(exp_params["essays"])} essays')
            
            # Recompute interface to ensure frontend gets updated essays data
            try:
                from routes.participant import update_participant_experiment_params
                participant = update_participant_experiment_params(participant, found_session)
                # Verify essays are still in experiment_params after interface update
                final_essays = participant.get('experiment_params', {}).get('essays', [])
                print(f'[Session] After interface update, participant {participant.get("id")} has {len(final_essays)} essays')
            except Exception as e:
                print(f'[Session] Error updating participant interface after essay upload: {e}')
                import traceback
                traceback.print_exc()
            
            updated_participants.append(participant)
        
        found_session['participants'] = updated_participants
        commit_session(session_key, found_session)
        
        # Broadcast update to all participants
        try:
            from websocket.handlers import broadcast_participant_update
            session_id_for_broadcast = found_session.get('session_id') or session_key
            broadcast_participant_update(
                session_id=session_id_for_broadcast,
                participants=participants,
                session_info=found_session,
                update_type='essays_updated'
            )
        except Exception as e:
            print(f'[Session] Error broadcasting essays update: {e}')
        
        return jsonify({
            'success': True,
            'uploaded_count': len(uploaded_essays),
            'essays': uploaded_essays,
            'total_essays': len(session_essays)
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Upload map files (images, PDF, TXT)
ALLOWED_MAP_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'pdf', 'txt'}

@session_bp.route('/api/sessions/<path:session_identifier>/upload_maps', methods=['POST'])
def upload_maps(session_identifier):
    try:
        from urllib.parse import unquote
        session_identifier = unquote(session_identifier)

        found_session = None
        session_key = None

        if session_identifier in sessions:
            found_session = sessions[session_identifier]
            session_key = session_identifier
        else:
            for sid, session in sessions.items():
                if session.get('session_name', '').lower() == session_identifier.lower():
                    found_session = session
                    session_key = sid
                    break

        if not found_session:
            return jsonify({'error': 'Session not found'}), 404

        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400

        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'maps')
        os.makedirs(upload_dir, exist_ok=True)

        # params can be a dict (from frontend) or a list (from experiment_config when experiment_type is set)
        params = found_session.get('params')
        if isinstance(params, dict):
            session_maps = list(params.get('maps', []) or [])
        else:
            session_maps = []

        uploaded_maps = []

        for file in files:
            if file.filename == '':
                continue

            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in ALLOWED_MAP_EXTENSIONS:
                return jsonify({'error': f'Invalid file type. Allowed: images, PDF, TXT. Received: {file.filename}'}), 400

            original_filename = file.filename
            safe_filename = secure_filename(original_filename)
            map_id = str(uuid.uuid4())
            file_extension = os.path.splitext(safe_filename)[1] or f'.{ext}'
            unique_filename = f"{map_id}{file_extension}"
            file_path = os.path.join(upload_dir, unique_filename)

            file.save(file_path)

            map_obj = {
                'id': map_id,
                'filename': unique_filename,
                'original_filename': original_filename,
                'file_path': f'/api/maps/{unique_filename}',
                'role': 'guide',
                'uploaded_at': _utc_now_iso_z()
            }

            uploaded_maps.append(map_obj)
            session_maps.append(map_obj)

        # Ensure params is a dict before storing maps (it may be a list from experiment_config)
        params = found_session.get('params')
        if isinstance(params, dict):
            params['maps'] = session_maps
        else:
            found_session['params'] = {'maps': session_maps}
        commit_session(session_key, found_session)

        return jsonify({
            'success': True,
            'uploaded_count': len(uploaded_maps),
            'maps': session_maps,
            'total_maps': len(session_maps)
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def _map_file_lookup_dirs():
    """Uploaded session maps first, then bundled presets (see map_assets/)."""
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return (
        os.path.join(backend_root, 'uploads', 'maps'),
        os.path.join(backend_root, 'map_assets'),
    )


# Serve map files
@session_bp.route('/api/maps/<filename>', methods=['GET'])
def serve_map(filename):
    """
    Map images for Map Task. Primary: uploads/maps (UUID names after researcher upload).
    Fallback: backend/map_assets/ for preset filenames (e.g. map2_follower.jpg) when session
    still references the original name or files were not re-uploaded after a container reset.
    """
    try:
        from flask import send_from_directory

        if not filename or '/' in filename or '\\' in filename or '..' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        safe = secure_filename(filename)
        if not safe:
            return jsonify({'error': 'Invalid filename'}), 400

        for directory in _map_file_lookup_dirs():
            if not os.path.isdir(directory):
                continue
            real_dir = os.path.realpath(directory)
            fp = os.path.join(directory, safe)
            if not os.path.isfile(fp):
                continue
            real_file = os.path.realpath(fp)
            if real_file == real_dir or not real_file.startswith(real_dir + os.sep):
                continue
            return send_from_directory(directory, safe)
        return jsonify({'error': 'Map not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 404

# Serve essay files
@session_bp.route('/api/essays/<filename>', methods=['GET'])
def serve_essay(filename):
    try:
        from flask import send_from_directory
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'essays')
        return send_from_directory(upload_dir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404
