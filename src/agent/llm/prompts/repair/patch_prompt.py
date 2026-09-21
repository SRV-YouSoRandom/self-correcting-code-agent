from __future__ import annotations

from agent.core.contract.schema import ExecutionContract
from agent.core.state import ErrorClassification

PATCH_SYSTEM_PROMPT = """You are the repair module of an autonomous code execution agent.
The previous code attempt failed with a specific, fixable error. Fix ONLY what is needed
to resolve this error while keeping the overall approach intact. Output ONLY the raw,
complete, corrected Python code, no markdown fences, no explanations.
"""


def build_patch_prompt(
    user_prompt: str,
    contract: ExecutionContract,
    previous_code: str,
    error: ErrorClassification,
    attempt_summaries: list[str],
) -> tuple[str, str]:
    history = "\n".join(attempt_summaries) if attempt_summaries else "No prior attempts."
    contract_json = contract.model_dump_json(indent=2)

    user_message = (
        f"User request:\n{user_prompt}\n\n"
        f"Execution contract:\n{contract_json}\n\n"
        f"Previous code:\n{previous_code}\n\n"
        f"Error category: {error.category.value}\n"
        f"Error detail:\n{error.truncated_traceback}\n\n"
        f"Attempt history:\n{history}\n\n"
        "Fix the specific error and return the complete corrected script now."
    )
    return PATCH_SYSTEM_PROMPT, user_message
