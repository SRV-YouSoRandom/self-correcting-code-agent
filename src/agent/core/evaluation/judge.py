from __future__ import annotations

import json
import re
from pathlib import Path

from agent.core.contract.schema import ExecutionContract
from agent.core.state import EvaluationLayer, EvaluationResult, ExecutionResult
from agent.llm.client import LLMClient
from agent.llm.prompts.judge_prompt import build_judge_prompt
from agent.llm.tiers import ModelTier

MAX_STDOUT_SUMMARY_CHARS = 1500
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _summarize_stdout(stdout: str) -> str:
    stripped = stdout.strip()
    if len(stripped) <= MAX_STDOUT_SUMMARY_CHARS:
        return stripped or "(no stdout output)"
    return stripped[:MAX_STDOUT_SUMMARY_CHARS] + "... (truncated)"


def _summarize_artifacts(artifact_paths: list[str]) -> str:
    if not artifact_paths:
        return "(no artifacts produced)"

    lines = []
    for path_str in artifact_paths:
        path = Path(path_str)
        if path.exists():
            size = path.stat().st_size
            lines.append(f"{path.name} ({size} bytes)")
        else:
            lines.append(f"{path.name} (missing)")
    return "\n".join(lines)


def _parse_judge_response(text: str) -> tuple[bool, str]:
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(cleaned)
        passed = bool(data.get("passed", False))
        reason = str(data.get("reason", ""))
        return passed, reason
    except (json.JSONDecodeError, AttributeError):
        return False, "Could not parse semantic judge response; treating as failure."


async def judge_semantic_success(
    user_prompt: str,
    contract: ExecutionContract,
    execution_result: ExecutionResult,
    llm_client: LLMClient,
    tier: ModelTier = ModelTier.CHEAP,
) -> EvaluationResult:
    if not contract.success_criteria.strip():
        return EvaluationResult(passed=True)

    stdout_summary = _summarize_stdout(execution_result.stdout)
    artifact_summary = _summarize_artifacts(execution_result.artifact_paths)

    system_prompt, user_message = build_judge_prompt(
        user_prompt=user_prompt,
        contract=contract,
        stdout_summary=stdout_summary,
        artifact_summary=artifact_summary,
    )

    response = await llm_client.generate(
        prompt=user_message,
        tier=tier,
        system_prompt=system_prompt,
    )

    passed, reason = _parse_judge_response(response.text)

    return EvaluationResult(
        passed=passed,
        failed_layer=None if passed else EvaluationLayer.SEMANTIC,
        reason=reason,
    )
