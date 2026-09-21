from __future__ import annotations

from agent.core.contract.schema import ExecutionContract

GENERATE_SYSTEM_PROMPT = """You are the code generation module of an autonomous code execution agent.
Write a single, complete, self-contained Python script that fulfills the user's request
and satisfies the given execution contract. Output ONLY the raw Python code, no markdown
fences, no explanations before or after.

Rules:
- The script must be runnable as-is with `python script.py`.
- Write any required output artifact to the exact filename specified in the contract.
- Handle errors gracefully where reasonable, but do not silently swallow failures needed
  for debugging.
- Only use packages that are commonly available or installable via pip.
- Do not access the filesystem outside the working directory.
"""


def build_generate_prompt(user_prompt: str, contract: ExecutionContract) -> tuple[str, str]:
    contract_json = contract.model_dump_json(indent=2)
    user_message = (
        f"User request:\n{user_prompt}\n\n"
        f"Execution contract:\n{contract_json}\n\n"
        "Write the Python script now."
    )
    return GENERATE_SYSTEM_PROMPT, user_message
