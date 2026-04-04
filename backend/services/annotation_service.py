"""
Annotation Service: Manages in-session annotation checkpoints.

Triggers can happen in two ways:
1) Action-triggered: when a participant performs a key action in a checkpoint window.
2) Forced-triggered: if no action-trigger happened, force popup in the late part of the window.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple

from routes.session import commit_session

# Checkpoint ranges: (min_pct, max_pct) for each of 3 checkpoints
# Widened from 5% to 15% windows so users don't miss triggers (e.g. 2-min session: 18s window vs 6s)
ANNOTATION_CHECKPOINT_RANGES = [
    (20, 25),   # Checkpoint 0: ~20% (15-30%)
    (45, 50),   # Checkpoint 1: ~45% (40-55%)
    (70, 75),   # Checkpoint 2: ~70% (65-80%)
]
# Force trigger in the last part of each checkpoint window.
# Example for 15-30: threshold = 30 - (30-15)*0.25 = 26.25%
FORCED_TRIGGER_WINDOW_RATIO = 0.05


def _parse_client_submitted_at_iso(raw: Optional[str]) -> Optional[datetime]:
    """Parse browser ISO-8601 submit time; return UTC-aware datetime or None if invalid."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def is_annotation_enabled(session: dict) -> bool:
    """Check if annotation is enabled for this session."""
    exp_config = session.get('experiment_config', {})
    annotation_config = exp_config.get('annotation', {})
    if isinstance(annotation_config, bool):
        return annotation_config
    return bool(annotation_config.get('enabled', False))


def get_session_progress_pct(session: dict) -> Optional[float]:
    """
    Get session progress as percentage (0-100).
    Uses remaining_seconds and duration to compute elapsed percentage.
    """
    remaining = session.get('remaining_seconds')
    duration_min = session.get('duration_minutes')
    if duration_min is None:
        # Fallback: try timer service
        try:
            from services.timer_service import get_timer
            session_id = session.get('session_id')
            if session_id:
                timer = get_timer(session_id)
                if timer:
                    duration_min = timer.initial_duration / 60
        except Exception:
            pass
    if remaining is None:
        # Fallback: try timer
        try:
            from services.timer_service import get_timer
            session_id = session.get('session_id')
            if session_id:
                timer = get_timer(session_id)
                if timer:
                    remaining = timer.get_remaining_seconds()
        except Exception:
            pass
    if remaining is None or duration_min is None:
        return None
    duration_sec = int(duration_min) * 60
    if duration_sec <= 0:
        return 0.0
    elapsed = duration_sec - int(remaining)
    elapsed = max(0, min(elapsed, duration_sec))
    return (elapsed / duration_sec) * 100.0


def get_current_checkpoint(session: dict) -> Optional[int]:
    """
    If session progress is within a checkpoint range, return that checkpoint index (0, 1, or 2).
    Otherwise return None.
    """
    progress = get_session_progress_pct(session)
    if progress is None:
        return None
    for idx, (lo, hi) in enumerate(ANNOTATION_CHECKPOINT_RANGES):
        if lo <= progress <= hi:
            return idx
    return None


def get_human_participant_ids(session: dict) -> list:
    """Get IDs of human participants (exclude AI agents)."""
    participants = session.get('participants', [])
    human_ids = []
    for p in participants:
        ptype = (p.get('type') or '').lower()
        if ptype not in ('ai', 'ai_agent'):
            pid = p.get('id') or p.get('participant_id')
            if pid:
                human_ids.append(pid)
    return human_ids


def should_trigger_annotation(
    session_key: str,
    session: dict,
    participant_id: str,
    action_type: str,
) -> Tuple[bool, Optional[int]]:
    """
    Determine if annotation should be triggered for this action.
    Returns (should_trigger, checkpoint_index).
    """
    enabled = is_annotation_enabled(session)
    if not enabled:
        print(f'[Annotation] Skip: annotation not enabled (experiment_config.annotation={session.get("experiment_config", {}).get("annotation")})')
        return False, None

    # Only human participants can trigger
    human_ids = get_human_participant_ids(session)
    if participant_id not in human_ids:
        print(f'[Annotation] Skip: participant {participant_id} not in human_ids {human_ids}')
        return False, None

    # Session must be running
    status = session.get('status')
    if status != 'running':
        print(f'[Annotation] Skip: session status is {status!r}, not running')
        return False, None

    # Already in annotation mode - don't trigger again
    if session.get('annotation_active'):
        return False, None

    # Check if we're in a checkpoint range
    progress = get_session_progress_pct(session)
    checkpoint = get_current_checkpoint(session)
    print(f'[Annotation] Check: action={action_type}, progress={progress}%, remaining={session.get("remaining_seconds")}, duration_min={session.get("duration_minutes")}, checkpoint={checkpoint}')
    if checkpoint is None:
        print(f'[Annotation] Skip: progress {progress}% not in any checkpoint range (15-30, 40-55, 65-80)')
        return False, None

    # Check if we've already triggered this checkpoint
    triggered = session.get('annotation_triggered_checkpoints', [])
    if checkpoint in triggered:
        print(f'[Annotation] Skip: checkpoint {checkpoint} already triggered')
        return False, None

    print(f'[Annotation] TRIGGER: checkpoint {checkpoint} for action {action_type}')
    return True, checkpoint


def trigger_annotation(
    session_key: str,
    session: dict,
    checkpoint_index: int,
    sessions_store: dict,
) -> None:
    """
    Pause session, set annotation state, and broadcast annotation_popup to all participants.
    Caller must pass the sessions dict to update.
    """
    from services.timer_service import pause_timer
    from websocket.handlers import get_socketio

    session_id = session.get('session_id') or session_key
    human_ids = get_human_participant_ids(session)

    # Pause timer
    pause_timer(session_id)

    # Update session state
    session['annotation_active'] = True
    session['annotation_checkpoint'] = checkpoint_index
    session['annotation_submitted'] = []
    session['status'] = 'paused'
    triggered = session.get('annotation_triggered_checkpoints', [])
    if checkpoint_index not in triggered:
        triggered.append(checkpoint_index)
    session['annotation_triggered_checkpoints'] = triggered
    commit_session(session_key, session)

    # Broadcast annotation popup to all participants
    socketio = get_socketio()
    socketio.emit('annotation_popup', {
        'session_id': session_id,
        'checkpoint_index': checkpoint_index,
        'human_participant_ids': human_ids,
    }, room=session_id)

    # Broadcast status change
    from websocket.handlers import broadcast_participant_update
    broadcast_participant_update(
        session_id=session_id,
        participants=session.get('participants', []),
        session_info=session,
        update_type='annotation_triggered',
    )


def check_and_force_trigger_annotation(
    session_key: str,
    session: dict,
    sessions_store: dict,
) -> Tuple[bool, Optional[int]]:
    """
    Force-trigger annotation in the late part of a checkpoint window when:
    - annotation is enabled,
    - session is running,
    - no annotation is active,
    - checkpoint has not been triggered yet.

    Returns (triggered, checkpoint_index).
    """
    if not is_annotation_enabled(session):
        return False, None
    if session.get('status') != 'running':
        return False, None
    if session.get('annotation_active'):
        return False, None

    progress = get_session_progress_pct(session)
    checkpoint = get_current_checkpoint(session)
    if progress is None or checkpoint is None:
        return False, None

    triggered = session.get('annotation_triggered_checkpoints', [])
    if checkpoint in triggered:
        return False, None

    lo, hi = ANNOTATION_CHECKPOINT_RANGES[checkpoint]
    force_start = hi - ((hi - lo) * FORCED_TRIGGER_WINDOW_RATIO)
    if progress < force_start:
        return False, None

    print(
        f'[Annotation] FORCE TRIGGER: checkpoint {checkpoint}, '
        f'progress={progress:.2f}%, window={lo}-{hi}, force_start={force_start:.2f}%'
    )
    trigger_annotation(session_key, session, checkpoint, sessions_store)
    return True, checkpoint


def submit_annotation(
    session_key: str,
    session: dict,
    participant_id: str,
    transcription: str,
    sessions_store: dict,
    *,
    submitted_at: Optional[str] = None,
) -> bool:
    """
    Record annotation submission. If all human participants have submitted, resume session.
    Returns True if session was resumed.
    """
    from services.timer_service import resume_timer
    from websocket.handlers import get_socketio, broadcast_participant_update

    if not session.get('annotation_active'):
        return False

    checkpoint = session.get('annotation_checkpoint', 0)
    submitted = set(session.get('annotation_submitted', []))
    submitted.add(participant_id)
    session['annotation_submitted'] = list(submitted)

    effective_created = _parse_client_submitted_at_iso(submitted_at) or datetime.now(timezone.utc)
    created_iso = effective_created.isoformat()

    # Store annotation data per participant
    annotations = session.get('annotation_data', {})
    if participant_id not in annotations:
        annotations[participant_id] = []
    annotations[participant_id].append({
        'checkpoint': checkpoint,
        'transcription': transcription,
        'created_at': created_iso,
    })
    session['annotation_data'] = annotations
    commit_session(session_key, session)

    try:
        actual_session_id = session.get('session_id') or session_key
        from services.db import persist_in_session_annotation

        persist_in_session_annotation(
            actual_session_id,
            participant_id,
            checkpoint,
            transcription,
            created_at=effective_created,
        )
    except Exception as db_err:
        print(f'[Annotation] in_session DB persist: {db_err}')

    human_ids = set(get_human_participant_ids(session))
    if submitted >= human_ids:
        # All submitted - resume session
        session_id = session.get('session_id') or session_key
        session['annotation_active'] = False
        session['annotation_checkpoint'] = None
        session['annotation_submitted'] = []
        session['status'] = 'running'
        commit_session(session_key, session)

        resume_timer(session_id)

        socketio = get_socketio()
        socketio.emit('annotation_resume', {
            'session_id': session_id,
        }, room=session_id)

        broadcast_participant_update(
            session_id=session_id,
            participants=session.get('participants', []),
            session_info=session,
            update_type='annotation_completed',
        )
        return True
    return False
