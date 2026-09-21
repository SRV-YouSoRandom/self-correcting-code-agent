from __future__ import annotations

from dataclasses import dataclass

from agent.core.state import RetryBudget, RetryTier, SessionState, TokenBudget


@dataclass
class BudgetCheck:
    can_continue: bool
    reason: str = ""


def check_token_budget(token_budget: TokenBudget) -> BudgetCheck:
    if token_budget.exceeded():
        return BudgetCheck(
            can_continue=False,
            reason=f"Token budget exhausted ({token_budget.used_total}/{token_budget.max_total_tokens} used).",
        )
    return BudgetCheck(can_continue=True)


def check_retry_budget(retry_budget: RetryBudget, tier: RetryTier) -> BudgetCheck:
    if not retry_budget.can_retry(tier):
        return BudgetCheck(
            can_continue=False,
            reason=f"Retry budget exhausted for tier '{tier.value}'.",
        )
    return BudgetCheck(can_continue=True)


def check_can_retry(session: SessionState, tier: RetryTier) -> BudgetCheck:
    token_check = check_token_budget(session.token_budget)
    if not token_check.can_continue:
        return token_check

    retry_check = check_retry_budget(session.retry_budget, tier)
    if not retry_check.can_continue:
        return retry_check

    return BudgetCheck(can_continue=True)


def record_attempt_cost(session: SessionState, tier: RetryTier, prompt_tokens: int, completion_tokens: int) -> None:
    session.token_budget.record(prompt_tokens, completion_tokens)
    session.retry_budget.record(tier)
