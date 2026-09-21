from __future__ import annotations

from agent.core.contract.validators import validate_contract_layer, validate_execution_layer
from agent.core.evaluation.judge import judge_semantic_success
from agent.core.state import SessionState, SessionStatus
from agent.llm.client import LLMClient
from agent.llm.tiers import ModelTier


async def evaluate(session: SessionState, llm_client: LLMClient) -> SessionState:
    attempt = session.latest_attempt()
    if attempt is None or attempt.execution_result is None or session.contract is None:
        session.status = SessionStatus.FAILED
        session.final_result = "No attempt available to evaluate."
        session.touch()
        return session

    execution_result = attempt.execution_result

    result = validate_execution_layer(execution_result)
    if not result.passed:
        attempt.evaluation_result = result
        session.status = SessionStatus.REFLECTING
        session.touch()
        return session

    result = validate_contract_layer(session.contract, execution_result)
    if not result.passed:
        attempt.evaluation_result = result
        session.status = SessionStatus.REFLECTING
        session.touch()
        return session

    result = await judge_semantic_success(
        user_prompt=session.prompt,
        contract=session.contract,
        execution_result=execution_result,
        llm_client=llm_client,
        tier=ModelTier.CHEAP,
    )
    attempt.evaluation_result = result

    if result.passed:
        session.status = SessionStatus.SUCCEEDED
        session.final_result = "Execution succeeded and satisfied the contract."
    else:
        session.status = SessionStatus.REFLECTING

    session.touch()
    return session
