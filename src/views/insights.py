"""Insights: predicted score, trajectory, diagnosis, and the skill map."""

import streamlit as st

from src.components.common import empty_state, metric_card, section_header, topic_row
from src.helpers import status_for_accuracy
from src.html_utils import esc, render_html
from src.metrics import _section_scaled, skill_stats
from src.state import go_to, quick_session_config, start_session


def render():
    history = st.session_state.history

    section_header(
        "Insights",
        "The story your practice is telling",
        "Every number here comes straight from the questions you've answered.",
    )

    if not history:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Nothing to chart just yet</div>
                <div class="card-subtitle">
                    Answer a handful of practice questions and your score
                    trajectory, pacing, and skill map will start filling in here.
                </div>
                """
            )
        if st.button("Start practicing →", type="primary"):
            start_session(quick_session_config())
            go_to("Practice")
        return

    math_score = _section_scaled(history, "math")
    rw_score = _section_scaled(history, "reading_writing")
    avg_seconds = (
        sum(e["seconds"] for e in history) / len(history) if history else 0
    )

    metric_columns = st.columns(4)
    with metric_columns[0]:
        metric_card(
            "Predicted score",
            st.session_state.predicted_score,
            f"Target is {st.session_state.target_score}",
            "↗",
        )
    with metric_columns[1]:
        metric_card(
            "Math (est.)",
            math_score if math_score is not None else "—",
            "Scaled from your accuracy",
            "∑",
        )
    with metric_columns[2]:
        metric_card(
            "Reading & Writing (est.)",
            rw_score if rw_score is not None else "—",
            "Scaled from your accuracy",
            "✎",
        )
    with metric_columns[3]:
        metric_card(
            "Pacing",
            f"{avg_seconds:.0f}s",
            "Average time per question",
            "◷",
        )

    section_header(
        "Progress",
        "Score trajectory",
        "Your estimated total after each completed session.",
    )

    with st.container(border=True):
        if len(st.session_state.score_history) >= 2:
            st.line_chart(st.session_state.score_history)
        else:
            empty_state(
                "Finish at least two sessions and your trajectory will "
                "appear here."
            )

    # Weekly diagnosis + score opportunity.
    diagnosis_col, opportunity_col = st.columns([1.4, 1], gap="large")

    stats = skill_stats(history)
    weak = [s for s, r in stats.items() if r["acc"] < 65]
    strong = [s for s, r in stats.items() if r["acc"] >= 80]

    with diagnosis_col:
        if weak:
            diagnosis = (
                "The clearest opportunity right now is "
                f"{weak[0]}"
                + (
                    f", followed by {weak[1]}."
                    if len(weak) > 1 else "."
                )
                + " Steady, focused reps on your softest skills tend to move "
                "your score faster than anything else."
            )
        else:
            diagnosis = (
                "No skill is dragging right now — you're fairly even across "
                "the board. This is a great moment to push difficulty up a "
                "notch and build stamina."
            )
        render_html(
            f"""
            <div class="ai-insight">
                <div class="ai-insight-label">This week's diagnosis</div>
                <h3>Where your points are hiding</h3>
                <p>{esc(diagnosis)}</p>
            </div>
            """
        )

    with opportunity_col:
        gap = max(
            0,
            int(st.session_state.target_score)
            - int(st.session_state.predicted_score or 0),
        )
        with st.container(border=True):
            metric_card(
                "Score opportunity",
                f"{gap} pts",
                "Between your estimate and your target",
                "◎",
            )

    # Skill map.
    section_header(
        "Skill map",
        "What's strong and what needs love",
        "Grouped by your current accuracy on each skill.",
    )

    weak_col, strong_col = st.columns(2, gap="large")

    with weak_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Needs attention</div>
                <div class="card-subtitle">Skills under 65% accuracy</div>
                """
            )
            ranked_weak = sorted(
                ((s, r) for s, r in stats.items() if r["acc"] < 65),
                key=lambda kv: kv[1]["acc"],
            )
            if ranked_weak:
                for skill, record in ranked_weak:
                    topic_row(skill, record["acc"],
                              status_for_accuracy(record["acc"]))
            else:
                empty_state("Nothing under 65% — lovely work.")

    with strong_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Strengths to protect</div>
                <div class="card-subtitle">Skills at 80% accuracy or higher</div>
                """
            )
            ranked_strong = sorted(
                ((s, r) for s, r in stats.items() if r["acc"] >= 80),
                key=lambda kv: kv[1]["acc"],
                reverse=True,
            )
            if ranked_strong:
                for skill, record in ranked_strong:
                    topic_row(skill, record["acc"],
                              status_for_accuracy(record["acc"]))
            else:
                empty_state(
                    "No skill is at 80% yet — keep going, you'll get there."
                )
