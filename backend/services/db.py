"""
PostgreSQL persistence for experiment action logs (SQLAlchemy 2.x).

Connection via DATABASE_URL or PGUSER/PGPASSWORD/PGHOST/PGPORT/PGDATABASE.

All ORM tables live in a dedicated PostgreSQL schema (default: humanagent_collab) so this
app can share a database with other systems without touching public.* or other schemas.
Set PGSCHEMA or DATABASE_SCHEMA to choose the namespace (alphanumeric + underscore only).
"""

from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from sqlalchemy import DateTime, Index, Integer, MetaData, String, Text, UniqueConstraint, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

_SCHEMA_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$')
_DEFAULT_SCHEMA = 'humanagent_collab'


def get_app_schema() -> str:
    """
    PostgreSQL schema that owns all tables for this application.
    Invalid or empty values fall back to the default (never silently use public).
    """
    raw = (os.environ.get('PGSCHEMA') or os.environ.get('DATABASE_SCHEMA') or _DEFAULT_SCHEMA).strip()
    if not raw or not _SCHEMA_NAME_RE.match(raw):
        return _DEFAULT_SCHEMA
    return raw.lower()


# Single metadata with schema so every model is qualified as {schema}.table_name
_metadata = MetaData(schema=get_app_schema())


class Base(DeclarativeBase):
    metadata = _metadata


class ActionLogRow(Base):
    __tablename__ = 'action_logs'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    participant_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (Index('ix_action_logs_session_created', 'session_id', 'created_at'),)


class InSessionAnnotationRow(Base):
    """In-session checkpoint pop-up transcriptions (separate from action_logs)."""

    __tablename__ = 'in_session_annotations'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    participant_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    checkpoint_index: Mapped[int] = mapped_column(Integer, nullable=False)
    transcription: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index('ix_in_session_ann_session_created', 'session_id', 'created_at'),)


class PostSessionAnnotationRow(Base):
    """Post-session annotation UI answers (per participant); separate from action_logs."""

    __tablename__ = 'post_session_annotations'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    participant_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            'session_id', 'participant_id', name='uq_post_session_annotations_session_participant'
        ),
    )


class ResearchSessionRow(Base):
    """Full researcher session state (params, interaction, participants, runtime fields)."""

    __tablename__ = 'research_sessions'

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


_engine = None
_SessionLocal: Optional[sessionmaker] = None


def _normalize_database_url(url: str) -> str:
    """Ensure psycopg2 driver for SQLAlchemy (docker / RDS often use postgresql:// only)."""
    u = url.strip()
    if u.startswith('postgresql://') and not u.startswith('postgresql+'):
        return 'postgresql+psycopg2://' + u[len('postgresql://') :]
    return u


def get_database_url() -> Optional[str]:
    url = (os.environ.get('DATABASE_URL') or '').strip()
    if url:
        return _normalize_database_url(url)
    host = (os.environ.get('PGHOST') or '').strip()
    if not host:
        return None
    user = quote_plus(os.environ.get('PGUSER') or '')
    password = quote_plus(os.environ.get('PGPASSWORD') or '')
    port = os.environ.get('PGPORT') or '5432'
    database = quote_plus(os.environ.get('PGDATABASE') or '')
    return f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'


def is_db_configured() -> bool:
    return get_database_url() is not None


def get_engine():
    global _engine
    if _engine is None:
        url = get_database_url()
        if not url:
            raise RuntimeError('Database is not configured')
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def init_db() -> None:
    """Create application schema (if needed) and tables if they do not exist."""
    schema = get_app_schema()
    engine = get_engine()
    # Identifier is regex-validated; safe to interpolate as bare PostgreSQL identifier.
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {schema}'))
    Base.metadata.create_all(bind=engine)


def _parse_entry_timestamp(ts: Optional[str]) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    try:
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def persist_action_log(entry: Dict[str, Any]) -> None:
    """Insert one action log row (idempotent on action_id)."""
    if not is_db_configured():
        return
    action_id = entry.get('action_id')
    session_id = entry.get('session_id')
    participant_id = entry.get('participant_id')
    if not action_id or not session_id or not participant_id:
        return
    SessionLocal = get_session_factory()
    row = ActionLogRow(
        action_id=action_id,
        session_id=session_id,
        participant_id=participant_id,
        created_at=_parse_entry_timestamp(entry.get('timestamp')),
        payload=entry,
    )
    with SessionLocal() as db:
        existing = db.scalar(select(ActionLogRow).where(ActionLogRow.action_id == action_id))
        if existing:
            return
        db.add(row)
        db.commit()


def load_session_logs(session_id: str) -> List[Dict[str, Any]]:
    """Return all action payloads for a session, ordered by time."""
    if not is_db_configured():
        return []
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        rows = db.scalars(
            select(ActionLogRow)
            .where(ActionLogRow.session_id == session_id)
            .order_by(ActionLogRow.created_at.asc())
        ).all()
        return [dict(r.payload) for r in rows]


def persist_in_session_annotation(
    session_id: str,
    participant_id: str,
    checkpoint_index: int,
    transcription: str,
) -> None:
    if not is_db_configured():
        return
    if not session_id or not participant_id or not transcription:
        return
    SessionLocal = get_session_factory()
    now = datetime.now(timezone.utc)
    row = InSessionAnnotationRow(
        session_id=session_id,
        participant_id=participant_id,
        checkpoint_index=int(checkpoint_index),
        transcription=transcription,
        created_at=now,
    )
    with SessionLocal() as db:
        db.add(row)
        db.commit()


def load_in_session_annotations(session_id: str, participant_id: str) -> List[Dict[str, Any]]:
    """In-session annotations for one participant, chronological."""
    if not is_db_configured():
        return []
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        rows = db.scalars(
            select(InSessionAnnotationRow)
            .where(
                InSessionAnnotationRow.session_id == session_id,
                InSessionAnnotationRow.participant_id == participant_id,
            )
            .order_by(InSessionAnnotationRow.created_at.asc())
        ).all()
        out = []
        for r in rows:
            ts = r.created_at.isoformat() if r.created_at else ''
            out.append(
                {
                    'checkpoint_index': r.checkpoint_index,
                    'transcription': r.transcription,
                    'created_at': ts,
                }
            )
        return out


def upsert_post_session_annotations(
    session_id: str, participant_id: str, annotations: Dict[str, Any]
) -> None:
    if not is_db_configured():
        return
    if not session_id or not participant_id:
        return
    SessionLocal = get_session_factory()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        row = db.scalar(
            select(PostSessionAnnotationRow).where(
                PostSessionAnnotationRow.session_id == session_id,
                PostSessionAnnotationRow.participant_id == participant_id,
            )
        )
        if row:
            row.payload = dict(annotations)
            row.updated_at = now
        else:
            db.add(
                PostSessionAnnotationRow(
                    session_id=session_id,
                    participant_id=participant_id,
                    payload=dict(annotations),
                    updated_at=now,
                )
            )
        db.commit()


def load_post_session_annotations(session_id: str, participant_id: str) -> Dict[str, Any]:
    """Return saved post-session annotation object (action_id -> fields), or {}."""
    if not is_db_configured():
        return {}
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        row = db.scalar(
            select(PostSessionAnnotationRow).where(
                PostSessionAnnotationRow.session_id == session_id,
                PostSessionAnnotationRow.participant_id == participant_id,
            )
        )
        if not row or not row.payload:
            return {}
        return dict(row.payload)


def _json_safe_payload(d: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(d, default=str))
    except Exception:
        return dict(d)


def persist_research_session(session_dict: Dict[str, Any]) -> None:
    """Upsert full session JSON (researcher UI + participants + runtime fields)."""
    if not is_db_configured():
        return
    sid = session_dict.get('session_id')
    if not sid:
        return
    sn = (session_dict.get('session_name') or '')[:512]
    payload = _json_safe_payload(copy.deepcopy(session_dict))
    now = datetime.now(timezone.utc)
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        row = db.scalar(select(ResearchSessionRow).where(ResearchSessionRow.session_id == sid))
        if row:
            row.session_name = sn
            row.payload = payload
            row.updated_at = now
        else:
            db.add(
                ResearchSessionRow(
                    session_id=sid,
                    session_name=sn,
                    payload=payload,
                    updated_at=now,
                )
            )
        db.commit()


def delete_research_session(session_id: str) -> None:
    if not is_db_configured() or not session_id:
        return
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        row = db.scalar(select(ResearchSessionRow).where(ResearchSessionRow.session_id == session_id))
        if row:
            db.delete(row)
            db.commit()


def load_all_research_sessions() -> Dict[str, Dict[str, Any]]:
    """Return all sessions keyed by session_id (matches in-memory ``sessions`` dict keys)."""
    if not is_db_configured():
        return {}
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        rows = db.scalars(select(ResearchSessionRow)).all()
        out: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            if r.payload:
                out[r.session_id] = dict(r.payload)
        return out
