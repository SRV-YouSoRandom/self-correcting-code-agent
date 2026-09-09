from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from agent.core.contract.schema import ExecutionContract
from agent.core.errors.taxonomy import ErrorCategory, RepairStrategy


class SessionStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    REFLECTING = "reflecting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED_BUDGET = "aborted_budget"


class RetryTier(str, Enum):
    PATCH = "patch"
    RETHINK = "rethink"


class ExecutionResult(BaseModel):
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0
    artifact_paths: list[str] = Field(default_factory=list)


class EvaluationLayer(str, Enum):
    EXECUTION = "execution"
    CONTRACT = "contract"
    SEMANTIC = "semantic"


class EvaluationResult(BaseModel):
    passed: bool
    failed_layer: Optional[EvaluationLayer] = None
    reason: str = ""


class ErrorClassification(BaseModel):
    category: ErrorCategory = ErrorCategory.UNKNOWN
    repair_strategy: RepairStrategy = RepairStrategy.PATCH
    exception_name: Optional[str] = None
    http_status: Optional[int] = None
    truncated_traceback: str = ""


class AttemptRecord(BaseModel):
    attempt_number: int
    code: str
    execution_result: Optional[ExecutionResult] = None
    evaluation_result: Optional[EvaluationResult] = None
    error_classification: Optional[ErrorClassification] = None
    model_tier_used: str = "cheap"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> str:
        if self.evaluation_result and self.evaluation_result.passed:
            return f"Attempt {self.attempt_number}: succeeded"
        category = self.error_classification.category.value if self.error_classification else "unknown"
        reason = self.evaluation_result.reason if self.evaluation_result else "no evaluation recorded"
        return f"Attempt {self.attempt_number}: failed ({category}) - {reason}"


class TokenBudget(BaseModel):
    max_total_tokens: int = 50_000
    used_prompt_tokens: int = 0
    used_completion_tokens: int = 0

    @property
    def used_total(self) -> int:
        return self.used_prompt_tokens + self.used_completion_tokens

    @property
    def remaining(self) -> int:
        return max(self.max_total_tokens - self.used_total, 0)

    def exceeded(self) -> bool:
        return self.used_total >= self.max_total_tokens

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.used_prompt_tokens += prompt_tokens
        self.used_completion_tokens += completion_tokens


class RetryBudget(BaseModel):
    max_patch_attempts: int = 3
    max_rethink_attempts: int = 2
    used_patch_attempts: int = 0
    used_rethink_attempts: int = 0

    def can_retry(self, tier: RetryTier) -> bool:
        if tier == RetryTier.PATCH:
            return self.used_patch_attempts < self.max_patch_attempts
        return self.used_rethink_attempts < self.max_rethink_attempts

    def record(self, tier: RetryTier) -> None:
        if tier == RetryTier.PATCH:
            self.used_patch_attempts += 1
        else:
            self.used_rethink_attempts += 1

    def exhausted(self) -> bool:
        patch_exhausted = self.used_patch_attempts >= self.max_patch_attempts
        rethink_exhausted = self.used_rethink_attempts >= self.max_rethink_attempts
        return patch_exhausted and rethink_exhausted


class SessionState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str
    status: SessionStatus = SessionStatus.PENDING

    contract: Optional[ExecutionContract] = None
    current_code: Optional[str] = None
    current_approach_summary: Optional[str] = None

    attempts: list[AttemptRecord] = Field(default_factory=list)

    token_budget: TokenBudget = Field(default_factory=TokenBudget)
    retry_budget: RetryBudget = Field(default_factory=RetryBudget)

    final_result: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def latest_attempt(self) -> Optional[AttemptRecord]:
        return self.attempts[-1] if self.attempts else None

    def attempt_history_summaries(self) -> list[str]:
        return [attempt.summary() for attempt in self.attempts]

    def next_attempt_number(self) -> int:
        return len(self.attempts) + 1

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)