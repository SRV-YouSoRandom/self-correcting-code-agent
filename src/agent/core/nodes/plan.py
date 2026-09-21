from __future__ import annotations

import json
import re

from agent.core.contract.schema import ExecutionContract
from agent.core.state import SessionState, SessionStatus
from agent.llm.client import LLMClient
from agent.llm.prompts.plan_prompt import build_plan_prompt
from agent.llm.tiers import ModelTier

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class PlanningError(Exception):
    pass


def _parse_contract(text: str) -> ExecutionContract:
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PlanningError(f"Planner returned invalid JSON: {exc}") from exc
    try:
        return ExecutionContract.model_validate(data)
    except Exception as exc:
        raise PlanningError(f"Planner JSON did not match contract schema: {exc}") from exc


async def plan(session: SessionState, llm_client: LLMClient) -> SessionState:
    system_prompt, user_message = build_plan_prompt(session.prompt)

    response = await llm_client.generate(
        prompt=user_message,
        tier=ModelTier.CHEAP,
        system_prompt=system_prompt,
    )
    session.token_budget.record(response.prompt_tokens, response.completion_tokens)

    try:
        contract = _parse_contract(response.text)
    except PlanningError as exc:
        session.status = SessionStatus.FAILED
        session.final_result = str(exc)
        session.touch()
        return session

    session.contract = contract
    session.status = SessionStatus.GENERATING
    session.touch()
    return session
