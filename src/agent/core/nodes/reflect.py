from __future__ import annotations

from agent.core.context.attempt_log import build_attempt_summaries
from agent.core.errors.classifier import classify_contract_failure, classify_execution_failure, classify_semantic_failure
from agent.core.nodes.generate import strip_code_fences
from agent.core.retry.budget import check_can_retry, record_attempt_cost
from agent.core.retry.router import decide_repair
from agent.core.state import EvaluationLayer, RetryTier, SessionState, SessionStatus
from agent.llm.client import LLMClient
from agent.llm.prompts.repair.patch_prompt import build_patch_prompt
from agent.llm.prompts.repair.rethink_prompt import build_rethink_prompt


async def reflect(session: SessionState, llm_client: LLMClient) -> SessionState:
    attempt = session.latest_attempt()
    if attempt is None or attempt.evaluation_result is None or session.contract is None:
        session.status = SessionStatus.FAILED
        session.final_result = "Nothing to reflect on."
        session.touch()
        return session

    evaluation = attempt.evaluation_result

    if evaluation.failed_layer == EvaluationLayer.SEMANTIC:
        error = classify_semantic_failure(evaluation.reason)
    elif evaluation.failed_layer == EvaluationLayer.CONTRACT:
        error = classify_contract_failure(evaluation.reason)
    else:
        error = classify_execution_failure(attempt.execution_result)

    attempt.error_classification = error

    decision = decide_repair(error, attempts_so_far=session.retry_budget.used_patch_attempts)

    budget_check = check_can_retry(session, decision.tier)
    if not budget_check.can_continue:
        session.status = SessionStatus.ABORTED_BUDGET
        session.final_result = budget_check.reason
        session.touch()
        return session

    attempt_summaries = build_attempt_summaries(session)

    if decision.tier == RetryTier.RETHINK:
        system_prompt, user_message = build_rethink_prompt(
            user_prompt=session.prompt,
            contract=session.contract,
            error=error,
            attempt_summaries=attempt_summaries,
        )
    else:
        system_prompt, user_message = build_patch_prompt(
            user_prompt=session.prompt,
            contract=session.contract,
            previous_code=attempt.code,
            error=error,
            attempt_summaries=attempt_summaries,
        )

    response = await llm_client.generate(
        prompt=user_message,
        tier=decision.model_tier,
        system_prompt=system_prompt,
    )

    record_attempt_cost(session, decision.tier, response.prompt_tokens, response.completion_tokens)
    attempt.model_tier_used = decision.model_tier.value
    attempt.prompt_tokens = response.prompt_tokens
    attempt.completion_tokens = response.completion_tokens

    session.current_code = strip_code_fences(response.text)
    session.status = SessionStatus.EXECUTING
    session.touch()
    return session
