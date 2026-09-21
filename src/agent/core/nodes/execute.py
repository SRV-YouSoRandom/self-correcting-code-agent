from __future__ import annotations

from agent.core.state import AttemptRecord, SessionState, SessionStatus
from agent.sandbox.runner import SandboxRunner


def execute(session: SessionState, sandbox_runner: SandboxRunner) -> SessionState:
    if session.contract is None or session.current_code is None:
        session.status = SessionStatus.FAILED
        session.final_result = "Cannot execute without a contract and generated code."
        session.touch()
        return session

    attempt_number = session.next_attempt_number()
    execution_result = sandbox_runner.run(
        code=session.current_code,
        contract=session.contract,
        session_id=session.session_id,
        attempt_number=attempt_number,
    )

    attempt = AttemptRecord(
        attempt_number=attempt_number,
        code=session.current_code,
        execution_result=execution_result,
    )
    session.attempts.append(attempt)
    session.status = SessionStatus.EVALUATING
    session.touch()
    return session
