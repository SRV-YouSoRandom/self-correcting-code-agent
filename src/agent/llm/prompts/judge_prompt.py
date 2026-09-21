from __future__ import annotations

from agent.core.contract.schema import ExecutionContract

JUDGE_SYSTEM_PROMPT = """You are the semantic evaluation module of an autonomous code execution agent.
The code has already executed successfully and passed structural checks. Your job is to
judge whether the output actually fulfills the user's original intent.

Output ONLY valid JSON in this exact structure, no prose, no markdown fences:
{
  "passed": true | false,
  "reason": "one or two sentences explaining the judgment"
}
"""


def build_judge_prompt(
    user_prompt: str,
    contract: ExecutionContract,
    stdout_summary: str,
    artifact_summary: str,
) -> tuple[str, str]:
    user_message = (
        f"User request:\n{user_prompt}\n\n"
        f"Success criteria:\n{contract.success_criteria}\n\n"
        f"Program stdout (summary):\n{stdout_summary}\n\n"
        f"Artifact summary:\n{artifact_summary}\n\n"
        "Judge whether this fulfills the user's intent now."
    )
    return JUDGE_SYSTEM_PROMPT, user_message
