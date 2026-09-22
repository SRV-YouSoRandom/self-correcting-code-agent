from __future__ import annotations

import asyncio

import streamlit as st

from agent.core.state import SessionState
from agent.orchestrators.langgraph.graph import LangGraphOrchestrator
from agent.orchestrators.plain.runner import PlainOrchestrator
from agent.ui.components.cost_summary import render_cost_summary
from agent.ui.components.session_replay import render_session_replay
from agent.ui.components.trace_view import render_full_trace

st.set_page_config(page_title="Self-Correcting Code Sandbox Agent", layout="wide")


def _run_session(prompt: str, orchestrator_choice: str) -> SessionState:
    if orchestrator_choice == "LangGraph":
        orchestrator = LangGraphOrchestrator()
    else:
        orchestrator = PlainOrchestrator()
    return asyncio.run(orchestrator.run(prompt))


def render_new_run_tab() -> None:
    st.markdown("#### Run a new task")

    prompt = st.text_area(
        "Describe the task",
        placeholder="e.g. Write a script that scrapes headlines from a news site and saves them to a CSV file.",
        height=100,
    )

    orchestrator_choice = st.radio(
        "Orchestrator",
        options=["Plain Python", "LangGraph"],
        horizontal=True,
    )

    run_clicked = st.button("Run agent", type="primary", disabled=not prompt.strip())

    if run_clicked:
        with st.spinner("Agent is planning, generating, and self-correcting..."):
            session = _run_session(prompt.strip(), orchestrator_choice)
        st.session_state["last_session"] = session

    last_session: SessionState | None = st.session_state.get("last_session")
    if last_session is not None:
        st.divider()
        render_cost_summary(last_session)
        st.divider()
        render_full_trace(last_session)


def main() -> None:
    st.title("Self-Correcting Code Sandbox Agent")
    st.caption("Autonomous agent that writes, runs, and self-corrects code in an isolated sandbox.")

    tab_new_run, tab_history = st.tabs(["New Run", "Session History"])

    with tab_new_run:
        render_new_run_tab()

    with tab_history:
        render_session_replay()


if __name__ == "__main__":
    main()
