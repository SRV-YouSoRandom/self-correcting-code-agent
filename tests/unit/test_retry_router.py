from __future__ import annotations

from agent.core.errors.taxonomy import ErrorCategory, RepairStrategy
from agent.core.retry.router import ESCALATION_THRESHOLD, decide_repair
from agent.core.state import ErrorClassification, RetryTier
from agent.llm.tiers import ModelTier


def _classification(category: ErrorCategory, strategy: RepairStrategy) -> ErrorClassification:
    return ErrorClassification(category=category, repair_strategy=strategy, exception_name="X")


def test_patch_strategy_maps_to_patch_tier() -> None:
    error = _classification(ErrorCategory.ENVIRONMENT, RepairStrategy.PATCH)
    decision = decide_repair(error, attempts_so_far=0)

    assert decision.tier == RetryTier.PATCH


def test_rethink_strategy_maps_to_rethink_tier() -> None:
    error = _classification(ErrorCategory.EXTERNAL, RepairStrategy.RETHINK)
    decision = decide_repair(error, attempts_so_far=0)

    assert decision.tier == RetryTier.RETHINK


def test_rethink_always_uses_strong_model_regardless_of_attempt_count() -> None:
    error = _classification(ErrorCategory.SEMANTIC, RepairStrategy.RETHINK)
    decision = decide_repair(error, attempts_so_far=0)

    assert decision.model_tier == ModelTier.STRONG


def test_patch_uses_cheap_model_before_escalation_threshold() -> None:
    error = _classification(ErrorCategory.RUNTIME, RepairStrategy.PATCH)
    decision = decide_repair(error, attempts_so_far=ESCALATION_THRESHOLD - 1)

    assert decision.model_tier == ModelTier.CHEAP


def test_patch_escalates_to_strong_model_at_threshold() -> None:
    error = _classification(ErrorCategory.RUNTIME, RepairStrategy.PATCH)
    decision = decide_repair(error, attempts_so_far=ESCALATION_THRESHOLD)

    assert decision.model_tier == ModelTier.STRONG


def test_patch_stays_strong_after_threshold() -> None:
    error = _classification(ErrorCategory.RUNTIME, RepairStrategy.PATCH)
    decision = decide_repair(error, attempts_so_far=ESCALATION_THRESHOLD + 5)

    assert decision.model_tier == ModelTier.STRONG
