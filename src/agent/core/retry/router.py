from __future__ import annotations

from dataclasses import dataclass

from agent.core.errors.taxonomy import RepairStrategy
from agent.core.state import ErrorClassification, RetryTier
from agent.llm.tiers import ModelTier

ESCALATION_THRESHOLD = 2


@dataclass
class RepairDecision:
    tier: RetryTier
    model_tier: ModelTier


def _retry_tier_for(repair_strategy: RepairStrategy) -> RetryTier:
    if repair_strategy == RepairStrategy.RETHINK:
        return RetryTier.RETHINK
    return RetryTier.PATCH


def _model_tier_for(retry_tier: RetryTier, attempts_so_far: int) -> ModelTier:
    if retry_tier == RetryTier.RETHINK:
        return ModelTier.STRONG
    if attempts_so_far >= ESCALATION_THRESHOLD:
        return ModelTier.STRONG
    return ModelTier.CHEAP


def decide_repair(error: ErrorClassification, attempts_so_far: int) -> RepairDecision:
    retry_tier = _retry_tier_for(error.repair_strategy)
    model_tier = _model_tier_for(retry_tier, attempts_so_far)
    return RepairDecision(tier=retry_tier, model_tier=model_tier)
