from __future__ import annotations

import streamlit as st

from agent.core.state import SessionState
from agent.persistence.db import list_sessions
from agent.ui.components.cost_summary import render_cost_summary
from agent.ui.components.trace_view import render_full_trace


def render_session_replay() -> None:
    st.markdown("#### Past sessions")
    sessions = list_sessions(limit=50)

    if not sessions:
        st.info("No past sessions found yet. Run one from the 'New Run' tab.")
        return

    options = {
        f"{s.status.value.upper()} — {s.prompt[:60]}{'...' if len(s.prompt) > 60 else ''} ({s.session_id[:8]})": s
        for s in sessions
    }

    selected_label = st.selectbox("Select a session to replay", options=list(options.keys()))
    if selected_label is None:
        return

    session: SessionState = options[selected_label]
    render_cost_summary(session)
    st.divider()
    render_full_trace(session)
