"""
Export session data from PostgreSQL.

1) User (human) actions only — full payloads as stored in action_logs.
2) Full bundle — human actions plus in-session and post-session annotations.

Resolve session by:
  - ``--session-id`` (UUID): use directly.
  - ``--session-name``: lookup ``research_sessions.session_name``; if that table is missing
    or empty, fall back to ``action_logs.payload->>'session_name'``.

Run locally (point DATABASE_URL at Postgres, e.g. host port mapped from Docker):
  cd backend && python -m scripts.export_session_data --session-name "test1"

Run inside the backend container (same DB as the app; recommended when DB only exists in Docker):
  docker compose exec backend python -m scripts.export_session_data --session-name "test1"

Copy exports from container to host (default output: /app/exports in the image):
  docker compose cp backend:/app/exports ./backend/exports

Requires DATABASE_URL or PG* env. Loads backend/.env if python-dotenv is installed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_BACKEND_ROOT, '.env'))
except ImportError:
    pass


def _safe_filename_part(name: str) -> str:
    s = re.sub(r'[^\w\-]+', '_', name.strip())[:80]
    return s or 'session'


def _resolve_session_ids(session_name: str) -> List[str]:
    from sqlalchemy.exc import ProgrammingError

    from services.db import (
        find_session_ids_by_name,
        find_session_ids_by_name_from_action_logs,
    )

    name = session_name.strip()
    ids: List[str] = []
    try:
        ids = find_session_ids_by_name(name)
    except ProgrammingError as e:
        err = str(e).lower()
        if 'research_sessions' in err or 'does not exist' in err:
            ids = []
        else:
            raise
    if not ids:
        ids = find_session_ids_by_name_from_action_logs(name)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description='Export session actions and annotations')
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument(
        '--session-name',
        help='Exact session_name (research_sessions or action_logs.payload.session_name)',
    )
    g.add_argument(
        '--session-id',
        help='Session UUID (skips name lookup)',
    )
    parser.add_argument(
        '--output-dir',
        default=os.path.join(_BACKEND_ROOT, 'exports'),
        help='Directory for JSON files (created if missing)',
    )
    args = parser.parse_args()

    from services.db import (
        is_db_configured,
        list_distinct_participant_ids,
        load_all_in_session_rows_for_session,
        load_all_post_session_rows_for_session,
        load_session_logs,
    )

    if not is_db_configured():
        print('export_session_data: DATABASE_URL or PG* not set; cannot read PostgreSQL.', file=sys.stderr)
        return 1

    if args.session_id:
        session_id = args.session_id.strip()
        label = session_id
        name_for_json = ''
    else:
        name = args.session_name.strip()
        ids = _resolve_session_ids(name)
        if not ids:
            print(
                f'export_session_data: no session found for session_name={name!r} '
                '(research_sessions and action_logs.payload.session_name).',
                file=sys.stderr,
            )
            return 2
        if len(ids) > 1:
            print(
                f'export_session_data: multiple session_ids for name {name!r}: {ids}. '
                'Pass --session-id to pick one.',
                file=sys.stderr,
            )
            return 3
        session_id = ids[0]
        label = name
        name_for_json = name

    all_entries = load_session_logs(session_id)
    if not name_for_json and all_entries:
        name_for_json = (all_entries[0].get('session_name') or '')[:512]
    human_actions = [e for e in all_entries if e.get('is_human') is True]

    os.makedirs(args.output_dir, exist_ok=True)
    prefix = _safe_filename_part(label) + '_' + session_id[:8]

    actions_path = os.path.join(args.output_dir, f'{prefix}_user_actions.json')
    bundle_path = os.path.join(args.output_dir, f'{prefix}_actions_and_annotations.json')

    with open(actions_path, 'w', encoding='utf-8') as f:
        json.dump(
            {
                'session_name': name_for_json,
                'session_id': session_id,
                'count': len(human_actions),
                'human_actions': human_actions,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    in_session_all = load_all_in_session_rows_for_session(session_id)
    post_all = load_all_post_session_rows_for_session(session_id)

    pid_set = set(list_distinct_participant_ids(session_id))
    for r in in_session_all:
        pid = r.get('participant_id')
        if pid:
            pid_set.add(pid)
    for r in post_all:
        pid = r.get('participant_id')
        if pid:
            pid_set.add(pid)
    participant_ids = sorted(pid_set)

    by_pid: Dict[str, Dict[str, Any]] = {}
    for pid in participant_ids:
        by_pid[pid] = {
            'human_actions': [e for e in human_actions if e.get('participant_id') == pid],
            'in_session_annotations': [r for r in in_session_all if r.get('participant_id') == pid],
            'post_session_annotations': next(
                (r.get('payload') or {} for r in post_all if r.get('participant_id') == pid),
                {},
            ),
        }

    bundle: Dict[str, Any] = {
        'session_name': name_for_json,
        'session_id': session_id,
        'participant_ids': participant_ids,
        'human_actions_all': human_actions,
        'in_session_annotations_all': in_session_all,
        'post_session_annotations_rows': post_all,
        'by_participant': by_pid,
    }

    with open(bundle_path, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)

    print('Wrote', actions_path)
    print('Wrote', bundle_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
