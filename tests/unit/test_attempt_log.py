from __future__ import annotations

from agent.core.context.attempt_log import (
    MAX_HISTORY_SUMMARIES,
    append_attempt,
    build_attempt_summaries,
    latest_code,
    latest_error,
)
from agent.core.errors.taxonomy import ErrorCategory, RepairStrategy
from agent.core.state import AttemptRecord, ErrorClassification, SessionState


def _attempt(number: int, code: str = "print('x')") -> AttemptRecord:
    return AttemptRecord(attempt_number=number, code=code)


def test_append_attempt_adds_to_session_and_touches_updated_at() -> None:
    session = SessionState(prompt="test")
    original_updated_at = session.updated_at

    append_attempt(session, _attempt(1))

    assert len(session.attempts) == 1
    assert session.updated_at >= original_updated_at


def test_latest_code_returns_none_when_no_attempts() -> None:
    session = SessionState(prompt="test")

    assert latest_code(session) is None


def test_latest_code_returns_most_recent_attempt_code() -> None:
    session = SessionState(prompt="test")
    append_attempt(session, _attempt(1, code="first"))
    append_attempt(session, _attempt(2, code="second"))

    assert latest_code(session) == "second"


def test_latest_error_returns_none_when_no_classification_set() -> None:
    session = SessionState(prompt="test")
    append_attempt(session, _attempt(1))

    assert latest_error(session) is None


def test_latest_error_returns_most_recent_classification() -> None:
    session = SessionState(prompt="test")
    attempt = _attempt(1)
    attempt.error_classification = ErrorClassification(
        category=ErrorCategory.RUNTIME, repair_strategy=RepairStrategy.PATCH
    )
    append_attempt(session, attempt)

    error = latest_error(session)
    assert error is not None
    assert error.category == ErrorCategory.RUNTIME


def test_build_attempt_summaries_returns_all_when_under_limit() -> None:
    session = SessionState(prompt="test")
    for i in range(3):
        append_attempt(session, _attempt(i + 1))

    summaries = build_attempt_summaries(session)

    assert len(summaries) == 3


def test_build_attempt_summaries_truncates_when_over_limit() -> None:
    session = SessionState(prompt="test")
    total_attempts = MAX_HISTORY_SUMMARIES + 5
    for i in range(total_attempts):
        append_attempt(session, _attempt(i + 1))

    summaries = build_attempt_summaries(session)

    assert len(summaries) == MAX_HISTORY_SUMMARIES + 1
    assert "omitted" in summaries[0]
    assert f"Attempt {total_attempts}" in summaries[-1]
