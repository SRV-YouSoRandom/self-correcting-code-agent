from __future__ import annotations

from agent.core.state import AttemptRecord, SessionState

MAX_HISTORY_SUMMARIES = 10


def build_attempt_summaries(session: SessionState) -> list[str]:
    summaries = session.attempt_history_summaries()
    if len(summaries) <= MAX_HISTORY_SUMMARIES:
        return summaries
    omitted = len(summaries) - MAX_HISTORY_SUMMARIES
    return [f"... ({omitted} earlier attempts omitted) ..."] + summaries[-MAX_HISTORY_SUMMARIES:]


def latest_code(session: SessionState) -> str | None:
    latest = session.latest_attempt()
    return latest.code if latest else None


def latest_error(session: SessionState):
    latest = session.latest_attempt()
    return latest.error_classification if latest else None


def append_attempt(session: SessionState, attempt: AttemptRecord) -> None:
    session.attempts.append(attempt)
    session.touch()
