from __future__ import annotations

from agent.core.errors.taxonomy import ErrorCategory
from agent.core.state import (
    AttemptRecord,
    ErrorClassification,
    EvaluationResult,
    RetryBudget,
    RetryTier,
    SessionState,
    TokenBudget,
)


def test_token_budget_not_exceeded_initially() -> None:
    budget = TokenBudget(max_total_tokens=1000)

    assert budget.exceeded() is False
    assert budget.remaining == 1000


def test_token_budget_records_usage_correctly() -> None:
    budget = TokenBudget(max_total_tokens=1000)
    budget.record(prompt_tokens=100, completion_tokens=50)

    assert budget.used_total == 150
    assert budget.remaining == 850


def test_token_budget_exceeded_when_usage_reaches_max() -> None:
    budget = TokenBudget(max_total_tokens=100)
    budget.record(prompt_tokens=60, completion_tokens=40)

    assert budget.exceeded() is True
    assert budget.remaining == 0


def test_token_budget_remaining_never_negative() -> None:
    budget = TokenBudget(max_total_tokens=100)
    budget.record(prompt_tokens=80, completion_tokens=80)

    assert budget.remaining == 0


def test_retry_budget_allows_patch_within_limit() -> None:
    budget = RetryBudget(max_patch_attempts=3)

    assert budget.can_retry(RetryTier.PATCH) is True


def test_retry_budget_blocks_patch_at_limit() -> None:
    budget = RetryBudget(max_patch_attempts=2)
    budget.record(RetryTier.PATCH)
    budget.record(RetryTier.PATCH)

    assert budget.can_retry(RetryTier.PATCH) is False


def test_retry_budget_patch_and_rethink_are_independent() -> None:
    budget = RetryBudget(max_patch_attempts=2, max_rethink_attempts=1)
    budget.record(RetryTier.PATCH)
    budget.record(RetryTier.PATCH)

    assert budget.can_retry(RetryTier.PATCH) is False
    assert budget.can_retry(RetryTier.RETHINK) is True


def test_retry_budget_exhausted_only_when_both_tiers_exhausted() -> None:
    budget = RetryBudget(max_patch_attempts=1, max_rethink_attempts=1)
    budget.record(RetryTier.PATCH)

    assert budget.exhausted() is False

    budget.record(RetryTier.RETHINK)

    assert budget.exhausted() is True


def test_attempt_summary_reports_success() -> None:
    attempt = AttemptRecord(attempt_number=1, code="print('x')")
    attempt.evaluation_result = EvaluationResult(passed=True)

    summary = attempt.summary()

    assert "succeeded" in summary
    assert "Attempt 1" in summary


def test_attempt_summary_reports_failure_with_category_and_reason() -> None:
    attempt = AttemptRecord(attempt_number=2, code="broken code")
    attempt.evaluation_result = EvaluationResult(passed=False, reason="file too small")
    attempt.error_classification = ErrorClassification(category=ErrorCategory.CONTRACT)

    summary = attempt.summary()

    assert "failed" in summary
    assert "contract" in summary
    assert "file too small" in summary


def test_session_next_attempt_number_increments_correctly() -> None:
    session = SessionState(prompt="test")
    assert session.next_attempt_number() == 1

    session.attempts.append(AttemptRecord(attempt_number=1, code="x"))
    assert session.next_attempt_number() == 2


def test_session_latest_attempt_returns_none_when_empty() -> None:
    session = SessionState(prompt="test")

    assert session.latest_attempt() is None


def test_session_attempt_history_summaries_matches_attempt_count() -> None:
    session = SessionState(prompt="test")
    session.attempts.append(AttemptRecord(attempt_number=1, code="x"))
    session.attempts.append(AttemptRecord(attempt_number=2, code="y"))

    summaries = session.attempt_history_summaries()

    assert len(summaries) == 2
