"""
Annotation Service: Manages in-session annotation checkpoints.

Triggers can happen in two ways:
1) Action-triggered: when a participant performs a key action in a checkpoint window.
2) Forced-triggered: if no action-trigger happened, force popup in the late part of the window.

Map Task (maptask): when a ground-truth route_pixel_ratio is set on session maps, checkpoints
follow follower route coverage (25% / 50% / 75% of GT). The popup requires: (1) reach the
milestone, (2) keep progress from decreasing for MAPTASK_ROUTE_STABILITY_SECONDS (erase resets
the window), (3) a follow-up human action then opens the popup if progress still qualifies.
"""

from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from routes.session import commit_session

# After crossing a route milestone, progress must stay stable (no decrease) for this many seconds,
# then the next human action opens the annotation popup.
MAPTASK_ROUTE_STABILITY_SECONDS = 5.0

from functions import route_pixel_ratio_from_map_filename

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

# Map task: milestone fractions of ground-truth route_pixel_ratio (checkpoint indices 0,1,2)
MAPTASK_ROUTE_CHECKPOINT_FRACTIONS = (0.25, 0.5, 0.75)


def _session_maps_list(session: dict) -> list:
    params = session.get('params')
    if isinstance(params, dict):
        m = params.get('maps')
        if isinstance(m, list):
            return m
    return []


def parse_route_pixel_ratio_optional(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v < 0 or v > 1.5:
        return None
    return v


def get_maptask_route_pixel_ratio_gt(session: dict) -> Optional[float]:
    """Prefer follower map entry; else any map with route_pixel_ratio or parseable filename."""
    maps = _session_maps_list(session)
    if not maps:
        return None

    def ratio_for_map(m: dict) -> Optional[float]:
        r = m.get('route_pixel_ratio')
        if r is not None:
            try:
                return float(r)
            except (TypeError, ValueError):
                pass
        fn = m.get('original_filename') or m.get('filename') or ''
        return route_pixel_ratio_from_map_filename(str(fn))

    follower = [
        m for m in maps
        if isinstance(m, dict) and (str(m.get('role') or '').strip().lower() == 'follower')
    ]
    for m in follower:
        got = ratio_for_map(m)
        if got is not None:
            return got
    for m in maps:
        if not isinstance(m, dict):
            continue
        got = ratio_for_map(m)
        if got is not None:
            return got
    return None


def _participant_role_lc(session: dict, participant_id: str) -> str:
    for p in session.get('participants', []) or []:
        pid = p.get('id') or p.get('participant_id')
        if pid == participant_id:
            return str(p.get('role') or '').strip().lower()
    return ''


def _next_untriggered_route_checkpoint(session: dict) -> Optional[int]:
    triggered = set(session.get('annotation_triggered_checkpoints', []))
    for i in range(len(MAPTASK_ROUTE_CHECKPOINT_FRACTIONS)):
        if i not in triggered:
            return i
    return None


def _event_time_from_client_optional(client_timestamp: Optional[str]) -> datetime:
    """Prefer browser time when valid, else server UTC."""
    if client_timestamp and isinstance(client_timestamp, str) and client_timestamp.strip():
        s = client_timestamp.strip()
        try:
            if s.endswith('Z'):
                s = s[:-1] + '+00:00'
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _annotations_maptask_dict(session: dict) -> dict:
    return session.setdefault('maptask_annotation', {})


def _update_maptask_follower_route_stability(
    session_key: str,
    session: dict,
    ratio: float,
    event_time: datetime,
    gt_ratio: float,
) -> None:
    """
    Follower-only: advance stability window (MAPTASK_ROUTE_STABILITY_SECONDS) toward arming pending_popup_checkpoint.
    If ratio drops below current milestone threshold or decreases vs last sample, reset window.
    """
    ann = _annotations_maptask_dict(session)
    i = _next_untriggered_route_checkpoint(session)
    if i is None:
        commit_session(session_key, session)
        return

    threshold = MAPTASK_ROUTE_CHECKPOINT_FRACTIONS[i] * gt_ratio
    last = ann.get('last_follower_ratio')
    stable_iso = ann.get('stable_since_iso')

    if ratio < threshold:
        ann['stable_since_iso'] = None
        ann['last_follower_ratio'] = ratio
        commit_session(session_key, session)
        return

    if ratio is not None and last is not None and ratio < float(last):
        ann['stable_since_iso'] = event_time.isoformat().replace('+00:00', 'Z')
        ann['last_follower_ratio'] = ratio
        commit_session(session_key, session)
        return

    if not stable_iso:
        ann['stable_since_iso'] = event_time.isoformat().replace('+00:00', 'Z')
        ann['last_follower_ratio'] = ratio
        commit_session(session_key, session)
        return

    t0 = _parse_client_submitted_at_iso(stable_iso) or event_time
    if (event_time - t0).total_seconds() >= MAPTASK_ROUTE_STABILITY_SECONDS:
        ann['pending_popup_checkpoint'] = i
        ann['stable_since_iso'] = None
        ann['last_follower_ratio'] = ratio
        print(
            f'[Annotation] MapTask: armed pending popup checkpoint {i} after '
            f'{MAPTASK_ROUTE_STABILITY_SECONDS}s stable progress (ratio={ratio:.6f})'
        )
    else:
        ann['last_follower_ratio'] = ratio

    commit_session(session_key, session)


def _parse_elapsed_seconds_optional(raw: Any) -> Optional[int]:
    """Session-timer elapsed at submit (initial_duration - remaining). Reject garbage."""
    if raw is None:
        return None
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    if v < 0 or v > 86400 * 7:
        return None
    return v


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


# Map task + in-session annotation: no real session time limit; internal timer uses this cap only.
MAPTASK_UNTIMED_TIMER_SECONDS = 7 * 24 * 3600


def is_maptask_untimed_annotation_session(session: dict) -> bool:
    """Map task with in-session annotation: unlimited wall time, dual submit ends session."""
    et = (session.get('experiment_type') or '').strip().lower()
    return et == 'maptask' and is_annotation_enabled(session)


def get_session_progress_pct(session: dict) -> Optional[float]:
    """
    Get session progress as percentage (0-100).
    Uses remaining_seconds and duration to compute elapsed percentage.
    """
    if session.get('maptask_untimed_timer'):
        return None
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
    *,
    route_pixel_ratio: Optional[float] = None,
    client_timestamp: Optional[str] = None,
) -> Tuple[bool, Optional[int]]:
    """
    Determine if annotation should be triggered for this action.
    Returns (should_trigger, checkpoint_index).

    Map task + ground-truth route ratio: (1) reach milestone progress, (2) keep progress from
    decreasing for MAPTASK_ROUTE_STABILITY_SECONDS (erase resets the window), (3) then any human
    action that still satisfies the milestone opens the popup.
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

    exp_type = (session.get('experiment_type') or '').strip().lower()
    gt_ratio = get_maptask_route_pixel_ratio_gt(session) if exp_type == 'maptask' else None

    if exp_type == 'maptask' and gt_ratio is not None and gt_ratio > 0:
        ratio_action = parse_route_pixel_ratio_optional(route_pixel_ratio)
        role_lc = _participant_role_lc(session, participant_id)
        if role_lc == 'follower' and ratio_action is not None:
            session['maptask_follower_route_pixel_ratio'] = ratio_action

        eff_ratio = parse_route_pixel_ratio_optional(session.get('maptask_follower_route_pixel_ratio'))
        event_time = _event_time_from_client_optional(client_timestamp)
        ann = _annotations_maptask_dict(session)
        pending = ann.get('pending_popup_checkpoint')
        i_next = _next_untriggered_route_checkpoint(session)

        if pending is not None and i_next is not None and pending != i_next:
            ann['pending_popup_checkpoint'] = None
            pending = None
            commit_session(session_key, session)

        if pending is not None:
            thr = MAPTASK_ROUTE_CHECKPOINT_FRACTIONS[int(pending)] * gt_ratio
            if eff_ratio is None or eff_ratio < thr:
                ann['pending_popup_checkpoint'] = None
                commit_session(session_key, session)
                if role_lc == 'follower' and ratio_action is not None:
                    _update_maptask_follower_route_stability(
                        session_key, session, ratio_action, event_time, gt_ratio
                    )
                return False, None

            ann['pending_popup_checkpoint'] = None
            ann['stable_since_iso'] = None
            ann['last_follower_ratio'] = None
            commit_session(session_key, session)
            print(
                f'[Annotation] TRIGGER (maptask route): checkpoint {pending} for action {action_type} '
                f'(after stable window + follow-up action, ratio={eff_ratio:.6f})'
            )
            return True, int(pending)

        if role_lc != 'follower' or ratio_action is None:
            return False, None

        _update_maptask_follower_route_stability(
            session_key, session, ratio_action, event_time, gt_ratio
        )
        return False, None

    # Timer-based checkpoints (default and maptask fallback when no GT on maps)
    progress = get_session_progress_pct(session)
    checkpoint = get_current_checkpoint(session)
    print(f'[Annotation] Check: action={action_type}, progress={progress}%, remaining={session.get("remaining_seconds")}, duration_min={session.get("duration_minutes")}, checkpoint={checkpoint}')
    if checkpoint is None:
        print(f'[Annotation] Skip: progress {progress}% not in any checkpoint range (15-30, 40-55, 65-80)')
        return False, None

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

    # Map task route milestones: reset stability arm state while checkpoint is active
    try:
        if (session.get('experiment_type') or '').strip().lower() == 'maptask' and get_maptask_route_pixel_ratio_gt(session):
            ann = _annotations_maptask_dict(session)
            ann['stable_since_iso'] = None
            ann['pending_popup_checkpoint'] = None
    except Exception:
        pass

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

    if (session.get('experiment_type') or '').strip().lower() == 'maptask':
        if get_maptask_route_pixel_ratio_gt(session) is not None:
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
    elapsed_seconds: Optional[int] = None,
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
    elapsed_val = _parse_elapsed_seconds_optional(elapsed_seconds)

    # Store annotation data per participant
    annotations = session.get('annotation_data', {})
    if participant_id not in annotations:
        annotations[participant_id] = []
    ann_entry = {
        'checkpoint': checkpoint,
        'transcription': transcription,
        'created_at': created_iso,
    }
    if elapsed_val is not None:
        ann_entry['elapsed_seconds'] = elapsed_val
    annotations[participant_id].append(ann_entry)
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
            elapsed_seconds=elapsed_val,
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
        if (session.get('experiment_type') or '').strip().lower() == 'maptask':
            ann = _annotations_maptask_dict(session)
            ann['stable_since_iso'] = None
            ann['pending_popup_checkpoint'] = None
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
