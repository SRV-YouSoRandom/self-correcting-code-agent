from __future__ import annotations

import pytest

from agent.core.state import SessionStatus
from agent.orchestrators.plain.runner import PlainOrchestrator

pytestmark = pytest.mark.integration

TERMINAL_STATUSES = {
    SessionStatus.SUCCEEDED,
    SessionStatus.FAILED,
    SessionStatus.ABORTED_BUDGET,
}


@pytest.mark.asyncio
async def test_simple_print_task_reaches_terminal_state() -> None:
    orchestrator = PlainOrchestrator()
    session = await orchestrator.run(
        "Write a script that prints the numbers 1 to 5, each on its own line.",
        persist=False,
    )

    assert session.status in TERMINAL_STATUSES
    assert session.prompt.startswith("Write a script")
    assert len(session.attempts) >= 1


@pytest.mark.asyncio
async def test_session_attempts_are_internally_consistent() -> None:
    orchestrator = PlainOrchestrator()
    session = await orchestrator.run(
        "Write a script that creates a JSON file named result.json containing a list of 3 integers.",
        persist=False,
    )

    for attempt in session.attempts:
        assert attempt.code.strip() != ""
        assert attempt.execution_result is not None
        if attempt.evaluation_result is not None and not attempt.evaluation_result.passed:
            assert attempt.error_classification is not None


@pytest.mark.asyncio
async def test_successful_session_has_valid_final_state() -> None:
    orchestrator = PlainOrchestrator()
    session = await orchestrator.run(
        "Write a script that prints 'hello world'.",
        persist=False,
    )

    if session.status == SessionStatus.SUCCEEDED:
        last_attempt = session.latest_attempt()
        assert last_attempt is not None
        assert last_attempt.evaluation_result is not None
        assert last_attempt.evaluation_result.passed is True
        assert session.final_result is not None


@pytest.mark.asyncio
async def test_token_budget_is_tracked_across_the_session() -> None:
    orchestrator = PlainOrchestrator()
    session = await orchestrator.run(
        "Write a script that prints the current attempt number, starting at 1.",
        persist=False,
    )

    assert session.token_budget.used_total > 0
    assert session.token_budget.used_total <= session.token_budget.max_total_tokens
