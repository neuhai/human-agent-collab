"""
Create PostgreSQL tables for action logs (SQLAlchemy).

Run from repo root or backend dir:
  cd backend && python -m scripts.init_db

Requires DATABASE_URL or PGUSER, PGPASSWORD, PGHOST, PGPORT, PGDATABASE in the environment.
Optional: PGSCHEMA (or DATABASE_SCHEMA) — PostgreSQL schema for this app’s tables (default humanagent_collab).
"""

from __future__ import annotations

import os
import sys

# Ensure backend package root is on path
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_BACKEND_ROOT, '.env'))
except ImportError:
    pass


def main() -> int:
    from services.db import get_app_schema, get_database_url, init_db, is_db_configured

    if not is_db_configured():
        print('init_db: skipped (no DATABASE_URL or PG* in environment)')
        return 0
    url = get_database_url()
    tail = url.split('@')[-1] if url and '@' in url else url
    schema = get_app_schema()
    print('init_db: connecting', tail, '| schema =', schema)
    init_db()
    print(
        'init_db: tables ready in schema',
        schema,
        '(action_logs, in_session_annotations, post_session_annotations, research_sessions)',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
