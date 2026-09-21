from __future__ import annotations

CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_SESSIONS_UPDATED_AT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions (updated_at DESC);
"""

SCHEMA_STATEMENTS: list[str] = [
    CREATE_SESSIONS_TABLE,
    CREATE_SESSIONS_UPDATED_AT_INDEX,
]
