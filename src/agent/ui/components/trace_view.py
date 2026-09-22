from __future__ import annotations

import streamlit as st

from agent.core.state import AttemptRecord, SessionState

STATUS_COLORS = {
    "succeeded": "green",
    "failed": "red",
    "aborted_budget": "orange",
}


def _status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "gray")
    return f":{color}[**{status.upper()}**]"


def render_session_header(session: SessionState) -> None:
    st.markdown(f"### {_status_badge(session.status.value)}")
    st.markdown(f"**Prompt:** {session.prompt}")
    if session.final_result:
        st.caption(session.final_result)
    st.divider()


def _render_execution_result(attempt: AttemptRecord) -> None:
    result = attempt.execution_result
    if result is None:
        return
    cols = st.columns(3)
    cols[0].metric("Exit code", result.exit_code if result.exit_code is not None else "n/a")
    cols[1].metric("Duration (s)", f"{result.duration_seconds:.2f}")
    cols[2].metric("Timed out", "yes" if result.timed_out else "no")

    if result.stdout.strip():
        with st.expander("stdout"):
            st.code(result.stdout, language="text")
    if result.stderr.strip():
        with st.expander("stderr"):
            st.code(result.stderr, language="text")
    if result.artifact_paths:
        st.caption(f"Artifacts: {', '.join(result.artifact_paths)}")


def _render_evaluation(attempt: AttemptRecord) -> None:
    evaluation = attempt.evaluation_result
    if evaluation is None:
        return
    if evaluation.passed:
        st.success(f"Evaluation passed. {evaluation.reason}")
    else:
        layer = evaluation.failed_layer.value if evaluation.failed_layer else "unknown"
        st.error(f"Evaluation failed at **{layer}** layer: {evaluation.reason}")


def _render_error_classification(attempt: AttemptRecord) -> None:
    error = attempt.error_classification
    if error is None:
        return
    st.warning(
        f"Category: **{error.category.value}** | "
        f"Repair strategy: **{error.repair_strategy.value}** | "
        f"Exception: {error.exception_name or 'n/a'}"
    )
    if error.truncated_traceback:
        with st.expander("Traceback / detail"):
            st.code(error.truncated_traceback, language="text")


def render_attempt(attempt: AttemptRecord) -> None:
    passed = attempt.evaluation_result.passed if attempt.evaluation_result else False
    icon = "✅" if passed else "❌"
    title = f"{icon} Attempt {attempt.attempt_number} — {attempt.model_tier_used} tier"

    with st.expander(title, expanded=not passed):
        st.code(attempt.code, language="python")
        _render_execution_result(attempt)
        _render_evaluation(attempt)
        _render_error_classification(attempt)
        if attempt.prompt_tokens or attempt.completion_tokens:
            st.caption(
                f"Tokens for this repair: {attempt.prompt_tokens} prompt + "
                f"{attempt.completion_tokens} completion"
            )


def render_full_trace(session: SessionState) -> None:
    render_session_header(session)
    for attempt in session.attempts:
        render_attempt(attempt)
