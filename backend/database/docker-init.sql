-- Runs once when the Postgres data volume is first created.
-- Tables are still created by the app (SQLAlchemy init_db); this only ensures the app schema exists early.
-- Must match default PGSCHEMA / DATABASE_SCHEMA (default: humanagent_collab).
CREATE SCHEMA IF NOT EXISTS humanagent_collab;
