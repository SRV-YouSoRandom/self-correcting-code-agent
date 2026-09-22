from __future__ import annotations

import pytest

from agent.core.state import SessionStatus
from agent.orchestrators.langgraph.graph import LangGraphOrchestrator
from agent.orchestrators.plain.runner import PlainOrchestrator

pytestmark = pytest.mark.integration

TERMINAL_STATUSES = {
    SessionStatus.SUCCEEDED,
    SessionStatus.FAILED,
    SessionStatus.ABORTED_BUDGET,
}

PARITY_PROMPT = "Write a script that prints the sum of numbers from 1 to 10."


@pytest.mark.asyncio
async def test_both_orchestrators_reach_terminal_state() -> None:
    plain_session = await PlainOrchestrator().run(PARITY_PROMPT, persist=False)
    langgraph_session = await LangGraphOrchestrator().run(PARITY_PROMPT, persist=False)

    assert plain_session.status in TERMINAL_STATUSES
    assert langgraph_session.status in TERMINAL_STATUSES


@pytest.mark.asyncio
async def test_both_orchestrators_produce_well_formed_attempts() -> None:
    plain_session = await PlainOrchestrator().run(PARITY_PROMPT, persist=False)
    langgraph_session = await LangGraphOrchestrator().run(PARITY_PROMPT, persist=False)

    for session in (plain_session, langgraph_session):
        assert len(session.attempts) >= 1
        for attempt in session.attempts:
            assert attempt.execution_result is not None
            assert attempt.code.strip() != ""


@pytest.mark.asyncio
async def test_both_orchestrators_produce_same_session_state_shape() -> None:
    plain_session = await PlainOrchestrator().run(PARITY_PROMPT, persist=False)
    langgraph_session = await LangGraphOrchestrator().run(PARITY_PROMPT, persist=False)

    plain_fields = set(plain_session.model_dump().keys())
    langgraph_fields = set(langgraph_session.model_dump().keys())

    assert plain_fields == langgraph_fields


@pytest.mark.asyncio
async def test_both_orchestrators_track_budgets_consistently() -> None:
    plain_session = await PlainOrchestrator().run(PARITY_PROMPT, persist=False)
    langgraph_session = await LangGraphOrchestrator().run(PARITY_PROMPT, persist=False)

    for session in (plain_session, langgraph_session):
        assert session.token_budget.used_total > 0
        assert session.token_budget.used_total <= session.token_budget.max_total_tokens
        assert session.retry_budget.used_patch_attempts <= session.retry_budget.max_patch_attempts
        assert session.retry_budget.used_rethink_attempts <= session.retry_budget.max_rethink_attempts
