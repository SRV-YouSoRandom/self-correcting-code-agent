from __future__ import annotations

from agent.core.contract.schema import ExecutionContract
from agent.core.state import ErrorClassification

RETHINK_SYSTEM_PROMPT = """You are the repair module of an autonomous code execution agent.
The previous approach has failed repeatedly or failed in a way that cannot be patched
(resource exhaustion, external blocking, or persistent semantic failure). Do NOT reuse
the previous approach. Design a genuinely different strategy to fulfill the user's
request and the execution contract. Output ONLY the raw, complete Python code for the
new approach, no markdown fences, no explanations.
"""


def build_rethink_prompt(
    user_prompt: str,
    contract: ExecutionContract,
    error: ErrorClassification,
    attempt_summaries: list[str],
) -> tuple[str, str]:
    history = "\n".join(attempt_summaries) if attempt_summaries else "No prior attempts."
    contract_json = contract.model_dump_json(indent=2)

    user_message = (
        f"User request:\n{user_prompt}\n\n"
        f"Execution contract:\n{contract_json}\n\n"
        f"Most recent failure category: {error.category.value}\n"
        f"Most recent failure detail:\n{error.truncated_traceback}\n\n"
        f"Full attempt history (do not repeat these approaches):\n{history}\n\n"
        "Design and write a fundamentally different approach now."
    )
    return RETHINK_SYSTEM_PROMPT, user_message
