from __future__ import annotations

from agent.core.nodes.evaluate import evaluate
from agent.core.nodes.execute import execute
from agent.core.nodes.generate import generate
from agent.core.nodes.plan import plan
from agent.core.nodes.reflect import reflect
from agent.core.state import SessionState, SessionStatus
from agent.llm.client import LLMClient
from agent.persistence.db import save_session
from agent.sandbox.runner import SandboxRunner

TERMINAL_STATUSES = {
    SessionStatus.SUCCEEDED,
    SessionStatus.FAILED,
    SessionStatus.ABORTED_BUDGET,
}


class PlainOrchestrator:
    def __init__(self, llm_client: LLMClient | None = None, sandbox_runner: SandboxRunner | None = None) -> None:
        self._llm_client = llm_client or LLMClient()
        self._sandbox_runner = sandbox_runner or SandboxRunner()

    async def run(self, prompt: str, persist: bool = True) -> SessionState:
        session = SessionState(prompt=prompt, status=SessionStatus.PLANNING)

        while session.status not in TERMINAL_STATUSES:
            session = await self._step(session)
            if persist:
                save_session(session)

        return session

    async def _step(self, session: SessionState) -> SessionState:
        if session.status == SessionStatus.PLANNING:
            return await plan(session, self._llm_client)

        if session.status == SessionStatus.GENERATING:
            return await generate(session, self._llm_client)

        if session.status == SessionStatus.EXECUTING:
            return execute(session, self._sandbox_runner)

        if session.status == SessionStatus.EVALUATING:
            return await evaluate(session, self._llm_client)

        if session.status == SessionStatus.REFLECTING:
            return await reflect(session, self._llm_client)

        raise RuntimeError(f"Unhandled session status: {session.status}")
