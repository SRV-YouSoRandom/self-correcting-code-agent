from __future__ import annotations

import streamlit as st

from agent.core.state import SessionState


def render_cost_summary(session: SessionState) -> None:
    st.markdown("#### Session cost")
    cols = st.columns(4)

    cols[0].metric(
        "Tokens used",
        f"{session.token_budget.used_total:,}",
        help=f"Budget: {session.token_budget.max_total_tokens:,}",
    )
    cols[1].metric(
        "Patch attempts",
        f"{session.retry_budget.used_patch_attempts}/{session.retry_budget.max_patch_attempts}",
    )
    cols[2].metric(
        "Rethink attempts",
        f"{session.retry_budget.used_rethink_attempts}/{session.retry_budget.max_rethink_attempts}",
    )
    cols[3].metric("Total attempts", len(session.attempts))

    remaining_ratio = session.token_budget.remaining / max(session.token_budget.max_total_tokens, 1)
    st.progress(min(max(1 - remaining_ratio, 0.0), 1.0), text="Token budget consumed")
