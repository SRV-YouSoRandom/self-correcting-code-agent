from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from agent.core.state import SessionState
from agent.persistence.models import SCHEMA_STATEMENTS

DEFAULT_DB_PATH = Path(os.environ.get("AGENT_DB_PATH", "agent_sessions.db"))


def _init_schema(connection: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.commit()


@contextmanager
def get_connection(db_path: Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _init_schema(connection)
        yield connection
    finally:
        connection.close()


def save_session(session: SessionState, db_path: Path = DEFAULT_DB_PATH) -> None:
    state_json = session.model_dump_json()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO sessions (session_id, prompt, status, state_json, created_at, updated_at)
            VALUES (:session_id, :prompt, :status, :state_json, :created_at, :updated_at)
            ON CONFLICT(session_id) DO UPDATE SET
                status = excluded.status,
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            {
                "session_id": session.session_id,
                "prompt": session.prompt,
                "status": session.status.value,
                "state_json": state_json,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            },
        )
        connection.commit()


def load_session(session_id: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[SessionState]:
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT state_json FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return SessionState.model_validate_json(row["state_json"])


def list_sessions(limit: int = 50, db_path: Path = DEFAULT_DB_PATH) -> list[SessionState]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT state_json FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [SessionState.model_validate_json(row["state_json"]) for row in rows]


def delete_session(session_id: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        connection.commit()
        return cursor.rowcount > 0
