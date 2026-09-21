from __future__ import annotations

from agent.core.state import SessionState, SessionStatus
from agent.llm.client import LLMClient
from agent.llm.prompts.generate_prompt import build_generate_prompt
from agent.llm.tiers import ModelTier

_PYTHON_FENCE = "```python"
_GENERIC_FENCE = "```"


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith(_PYTHON_FENCE):
        stripped = stripped[len(_PYTHON_FENCE):]
    elif stripped.startswith(_GENERIC_FENCE):
        stripped = stripped[len(_GENERIC_FENCE):]
    if stripped.endswith(_GENERIC_FENCE):
        stripped = stripped[: -len(_GENERIC_FENCE)]
    return stripped.strip()


async def generate(session: SessionState, llm_client: LLMClient) -> SessionState:
    if session.contract is None:
        session.status = SessionStatus.FAILED
        session.final_result = "Cannot generate code without an execution contract."
        session.touch()
        return session

    system_prompt, user_message = build_generate_prompt(session.prompt, session.contract)

    response = await llm_client.generate(
        prompt=user_message,
        tier=ModelTier.CHEAP,
        system_prompt=system_prompt,
    )
    session.token_budget.record(response.prompt_tokens, response.completion_tokens)

    session.current_code = strip_code_fences(response.text)
    session.status = SessionStatus.EXECUTING
    session.touch()
    return session
