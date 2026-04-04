"""
Action Logger: Logs human and agent actions to participant-specific files.

- Log entries: logs/{session_id}/{participant_id}.jsonl
- Binary files (screenshot, map_image, audio): logs/{session_id}/files/
  Datapoints reference files via mapping, e.g. "files/{action_id}_screenshot.png"
"""

import os
import json
import uuid
import base64
import re
import shutil
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from services.annotation_service import is_annotation_enabled


def utc_now_iso_z() -> str:
    """UTC instant as ISO-8601 with Z (matches browser Date parsing; avoids naive local vs UTC skew)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def coalesce_client_timestamp(client_iso: Optional[str], max_skew_seconds: float = 900.0) -> str:
    """
    Use browser-reported instant when parseable and within max_skew_seconds of server UTC.

    Map/chat actions wait for screenshots before HTTP/WebSocket; server-time-only timestamps
    were tens of seconds late vs AI logs, breaking post-annotation timelines.
    """
    now = datetime.now(timezone.utc)
    fallback = now.isoformat().replace("+00:00", "Z")
    if not client_iso or not isinstance(client_iso, str):
        return fallback
    s = client_iso.strip()
    if not s:
        return fallback
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        skew = abs((dt - now).total_seconds())
        if skew <= max_skew_seconds:
            return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        pass
    return fallback


def compute_session_elapsed_seconds(
    session: Optional[Dict[str, Any]], timer_session_id: str
) -> Optional[int]:
    """
    Elapsed session time as defined by the countdown timer: initial_duration - remaining_seconds.
    Matches the participant-visible timer (annotation / pause time does not advance this).
    """
    if not session or not timer_session_id:
        return None
    if not session.get('started_at'):
        return None

    remaining: Optional[int] = None
    initial: Optional[int] = None
    try:
        from services.timer_service import get_timer

        t = get_timer(timer_session_id)
        if t is not None:
            remaining = int(t.get_remaining_seconds())
            initial = int(t.initial_duration)
    except Exception:
        pass

    if remaining is None:
        raw = session.get('remaining_seconds')
        if raw is not None:
            try:
                remaining = int(raw)
            except (TypeError, ValueError):
                remaining = None

    if initial is None:
        try:
            from routes.participant import get_value_from_session_params

            dm = get_value_from_session_params(session, 'Session.Params.duration')
            if dm is None:
                dm = session.get('duration_minutes')
            if dm is None:
                return None
            initial = int(float(dm)) * 60
        except Exception:
            return None

    if remaining is None or initial is None:
        return None

    try:
        elapsed = int(initial) - int(remaining)
    except (TypeError, ValueError):
        return None
    return max(0, min(elapsed, int(initial)))


# Base directory for logs (relative to backend root)
LOGS_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
UPLOADS_AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'audio')

# Max size for inline html_snapshot in JSONL (bytes). Larger values are saved to file.
HTML_SNAPSHOT_INLINE_MAX = 32768


def _ensure_session_log_dir(session_id: str) -> str:
    """Ensure log directory exists for session, return path."""
    session_dir = os.path.join(LOGS_BASE_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def _ensure_session_files_dir(session_id: str) -> str:
    """Ensure files subdirectory exists for session, return path."""
    files_dir = os.path.join(LOGS_BASE_DIR, session_id, 'files')
    os.makedirs(files_dir, exist_ok=True)
    return files_dir


def _save_base64_to_file(session_id: str, action_id: str, field: str, data: str) -> Optional[str]:
    """
    Save base64-encoded image/data to session files folder.
    data: "data:image/png;base64,..." or "data:image/jpeg;base64,..."
    Returns relative path like "files/{action_id}_{field}.png" or None on error.
    """
    if not data or not isinstance(data, str):
        return None
    match = re.match(r'^data:([^;]+);base64,(.+)$', data.strip())
    if not match:
        return None
    mime, b64 = match.group(1), match.group(2)
    ext_map = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/jpg': '.jpg', 'image/gif': '.gif', 'image/webp': '.webp'}
    ext = ext_map.get(mime.lower(), '.png')
    try:
        file_bytes = base64.b64decode(b64)
    except Exception:
        return None
    files_dir = _ensure_session_files_dir(session_id)
    filename = f'{action_id}_{field}{ext}'
    file_path = os.path.join(files_dir, filename)
    try:
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        return f'files/{filename}'
    except Exception:
        return None


def _upload_annotation_screenshot_s3(session_id: str, action_id: str, data: str) -> Optional[str]:
    """data: data:image/...;base64,... -> s3 uri or None."""
    try:
        from services import s3_storage
        if not s3_storage.is_s3_configured():
            return None
        if not data or not isinstance(data, str):
            return None
        match = re.match(r'^data:([^;]+);base64,(.+)$', data.strip())
        if not match:
            return None
        mime, b64 = match.group(1), match.group(2)
        ext_map = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp'}
        ext = ext_map.get(mime.lower(), 'png')
        ct_map = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}
        content_type = ct_map.get(ext, 'image/png')
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return None
        key = s3_storage.build_annotation_key(session_id, action_id, f'screenshot.{ext}')
        return s3_storage.upload_bytes(key, raw, content_type)
    except Exception as e:
        print(f'[ActionLogger] Non-fatal S3 screenshot upload error: {e}')
        return None


def _upload_annotation_html_s3(session_id: str, action_id: str, content: str) -> Optional[str]:
    try:
        from services import s3_storage
        if not s3_storage.is_s3_configured():
            return None
        key = s3_storage.build_annotation_key(session_id, action_id, 'html_snapshot.html')
        return s3_storage.upload_bytes(key, content.encode('utf-8'), 'text/html; charset=utf-8')
    except Exception as e:
        print(f'[ActionLogger] Non-fatal S3 HTML upload error: {e}')
        return None


def _save_text_to_file(session_id: str, action_id: str, field: str, content: str) -> str:
    """Save text content to file, return relative path."""
    files_dir = _ensure_session_files_dir(session_id)
    filename = f'{action_id}_{field}.html'
    file_path = os.path.join(files_dir, filename)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f'files/{filename}'
    except Exception:
        return None


def _copy_audio_to_session_files(session_id: str, action_id: str, audio_url: str) -> Optional[str]:
    """
    Copy audio file from uploads/audio to session files folder.
    audio_url: e.g. "/api/audio/abc123.webm"
    Returns relative path like "files/{action_id}_audio.webm" or None.
    """
    if not audio_url or not isinstance(audio_url, str):
        return None
    # Extract filename from URL: /api/audio/xxx.webm -> xxx.webm
    parts = audio_url.strip().split('/')
    src_filename = parts[-1] if parts else None
    if not src_filename:
        return None
    src_path = os.path.join(UPLOADS_AUDIO_DIR, src_filename)
    if not os.path.isfile(src_path):
        return None
    ext = os.path.splitext(src_filename)[1] or '.webm'
    files_dir = _ensure_session_files_dir(session_id)
    dst_filename = f'{action_id}_audio{ext}'
    dst_path = os.path.join(files_dir, dst_filename)
    try:
        shutil.copy2(src_path, dst_path)
        return f'files/{dst_filename}'
    except Exception:
        return None


def _get_public_state(session: Dict[str, Any]) -> Dict[str, Any]:
    """Get public state visible to all participants."""
    return {
        'session_status': session.get('status', 'waiting'),
        'remaining_seconds': session.get('remaining_seconds'),
        'current_time': utc_now_iso_z()
    }


def _get_private_state(participant: Dict[str, Any]) -> Dict[str, Any]:
    """Get private state of participant (for agent logging)."""
    private_state = {}
    interface = participant.get('interface', {})
    for panel_group, panels in (interface or {}).items():
        if not isinstance(panels, list):
            continue
        for panel in panels:
            if not isinstance(panel, dict):
                continue
            for binding in panel.get('bindings', []):
                if not isinstance(binding, dict):
                    continue
                path = binding.get('path')
                value = binding.get('value')
                if path and path.startswith('Participant.'):
                    field_name = path.split('.', 1)[1]
                    private_state[field_name] = value
    if 'name' not in private_state:
        private_state['name'] = participant.get('name') or participant.get('participant_name')
    exp_params = participant.get('experiment_params', {})
    for key, value in exp_params.items():
        if key not in private_state:
            private_state[key] = value
    return private_state


def _build_session_status(session: Dict[str, Any], participant: Dict[str, Any]) -> Dict[str, Any]:
    """Build session_status (public + private) for agent actions."""
    return {
        'public_state': _get_public_state(session),
        'private_state': _get_private_state(participant)
    }


def log_action(
    session_id: str,
    participant_id: str,
    is_human: bool,
    action_type: str,
    action_content: str,
    result: str = 'success',
    metadata: Optional[Dict[str, Any]] = None,
    page: Optional[str] = None,
    experiment_type: Optional[str] = None,
    # Human-only
    screenshot: Optional[str] = None,
    html_snapshot: Optional[str] = None,
    # Agent-only
    session_status: Optional[Dict[str, Any]] = None,
    # Audio message
    audio_file_url: Optional[str] = None,
    # Map task (follower): current map drawing image
    map_image: Optional[str] = None,
    # For agent: pass session and participant to build session_status
    session: Optional[Dict[str, Any]] = None,
    participant: Optional[Dict[str, Any]] = None,
    # Browser event time (ISO with Z); avoids late timestamps after screenshot capture + queue
    client_timestamp: Optional[str] = None,
    # When set (e.g. WebSocket receive instant), overrides client_timestamp for one shared server clock
    event_timestamp_iso: Optional[str] = None,
) -> Optional[str]:
    """
    Append an action log entry to the participant's log file.
    Path: logs/{session_id}/{participant_id}.jsonl

    Returns action_id if successful, None on error.
    """
    try:
        action_id = str(uuid.uuid4())
        session_dir = _ensure_session_log_dir(session_id)

        if event_timestamp_iso and isinstance(event_timestamp_iso, str) and event_timestamp_iso.strip():
            entry_ts = event_timestamp_iso.strip()
        else:
            entry_ts = coalesce_client_timestamp(client_timestamp)
        entry = {
            'action_id': action_id,
            'timestamp': entry_ts,
            'session_id': session_id,
            'participant_id': participant_id,
            'session_name': session.get('session_name') if session else '',
            'participant_name': (participant.get('name') or participant.get('participant_name')) if participant else '',
            'is_human': is_human,
            'action_type': action_type,
            'action_content': action_content,
            'result': result,
            'metadata': metadata or {},
            'page': page,
            'experiment_type': experiment_type or '',
        }

        if session is not None:
            se = compute_session_elapsed_seconds(session, session_id)
            if se is not None:
                entry['session_elapsed_seconds'] = se

        if is_human:
            ann_mode = bool(session and is_annotation_enabled(session))
            use_s3_assets = ann_mode
            if screenshot is not None:
                if isinstance(screenshot, str) and screenshot.startswith('data:'):
                    if use_s3_assets:
                        s3_uri = _upload_annotation_screenshot_s3(session_id, action_id, screenshot)
                        if s3_uri:
                            entry['screenshot'] = s3_uri
                        else:
                            ref = _save_base64_to_file(session_id, action_id, 'screenshot', screenshot)
                            entry['screenshot'] = ref if ref else screenshot
                    else:
                        ref = _save_base64_to_file(session_id, action_id, 'screenshot', screenshot)
                        entry['screenshot'] = ref if ref else screenshot
                else:
                    entry['screenshot'] = screenshot
            if html_snapshot is not None:
                if use_s3_assets:
                    if len(html_snapshot) > HTML_SNAPSHOT_INLINE_MAX:
                        s3_uri = _upload_annotation_html_s3(session_id, action_id, html_snapshot)
                        if s3_uri:
                            entry['html_snapshot'] = s3_uri
                        else:
                            ref = _save_text_to_file(session_id, action_id, 'html_snapshot', html_snapshot)
                            entry['html_snapshot'] = ref
                    else:
                        s3_uri = _upload_annotation_html_s3(session_id, action_id, html_snapshot)
                        if s3_uri:
                            entry['html_snapshot'] = s3_uri
                        else:
                            entry['html_snapshot'] = html_snapshot
                else:
                    if len(html_snapshot) > HTML_SNAPSHOT_INLINE_MAX:
                        ref = _save_text_to_file(session_id, action_id, 'html_snapshot', html_snapshot)
                        entry['html_snapshot'] = ref
                    else:
                        entry['html_snapshot'] = html_snapshot
        else:
            # Agent: use session_status
            if session_status is None and session and participant:
                session_status = _build_session_status(session, participant)
            if session_status is not None:
                entry['session_status'] = session_status

        if audio_file_url:
            ref = _copy_audio_to_session_files(session_id, action_id, audio_file_url)
            entry['audio_file'] = ref if ref else audio_file_url

        if map_image:
            if isinstance(map_image, str) and map_image.startswith('data:'):
                ref = _save_base64_to_file(session_id, action_id, 'map_image', map_image)
                entry['map_image'] = ref if ref else map_image
            else:
                entry['map_image'] = map_image

        log_path = os.path.join(session_dir, f'{participant_id}.jsonl')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

        try:
            from services.db import is_db_configured, persist_action_log
            if is_db_configured():
                persist_action_log(entry)
        except Exception as db_err:
            print(f'[ActionLogger] DB persist skipped: {db_err}')

        return action_id
    except Exception as e:
        print(f'[ActionLogger] Error logging action: {e}')
        import traceback
        traceback.print_exc()
        return None


def attach_human_action_capture(
    session_id: str,
    participant_id: str,
    action_id: str,
    screenshot: Optional[str],
    html_snapshot: Optional[str],
    session: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Add screenshot / html_snapshot to an existing send_message row (jsonl rewrite).
    Used when the client sends text first (server-timed) then uploads capture asynchronously.
    """
    if screenshot is None and html_snapshot is None:
        return False
    log_path = os.path.join(LOGS_BASE_DIR, session_id, f'{participant_id}.jsonl')
    if not os.path.isfile(log_path):
        return False
    out_lines: list[str] = []
    found = False
    ann_mode = bool(session and is_annotation_enabled(session))
    use_s3_assets = ann_mode
    with open(log_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n\r')
            if not line.strip():
                continue
            try:
                ob = json.loads(line)
            except json.JSONDecodeError:
                out_lines.append(line)
                continue
            if ob.get('action_id') != action_id:
                out_lines.append(line)
                continue
            if str(ob.get('participant_id') or '') != str(participant_id):
                out_lines.append(line)
                continue
            found = True
            if screenshot is not None:
                if isinstance(screenshot, str) and screenshot.startswith('data:'):
                    if use_s3_assets:
                        s3_uri = _upload_annotation_screenshot_s3(session_id, action_id, screenshot)
                        if s3_uri:
                            ob['screenshot'] = s3_uri
                        else:
                            ref = _save_base64_to_file(session_id, action_id, 'screenshot', screenshot)
                            ob['screenshot'] = ref if ref else screenshot
                    else:
                        ref = _save_base64_to_file(session_id, action_id, 'screenshot', screenshot)
                        ob['screenshot'] = ref if ref else screenshot
                else:
                    ob['screenshot'] = screenshot
            if html_snapshot is not None:
                if use_s3_assets:
                    if len(html_snapshot) > HTML_SNAPSHOT_INLINE_MAX:
                        s3_uri = _upload_annotation_html_s3(session_id, action_id, html_snapshot)
                        if s3_uri:
                            ob['html_snapshot'] = s3_uri
                        else:
                            ref = _save_text_to_file(session_id, action_id, 'html_snapshot', html_snapshot)
                            ob['html_snapshot'] = ref
                    else:
                        s3_uri = _upload_annotation_html_s3(session_id, action_id, html_snapshot)
                        if s3_uri:
                            ob['html_snapshot'] = s3_uri
                        else:
                            ob['html_snapshot'] = html_snapshot
                else:
                    if len(html_snapshot) > HTML_SNAPSHOT_INLINE_MAX:
                        ref = _save_text_to_file(session_id, action_id, 'html_snapshot', html_snapshot)
                        ob['html_snapshot'] = ref
                    else:
                        ob['html_snapshot'] = html_snapshot
            out_lines.append(json.dumps(ob, ensure_ascii=False))
    if not found:
        return False
    with open(log_path, 'w', encoding='utf-8') as f:
        for L in out_lines:
            f.write(L + '\n')
    return True
