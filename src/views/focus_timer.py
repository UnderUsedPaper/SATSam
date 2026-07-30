"""Focus Timer: the full-size persistent timer plus an intention panel."""

import streamlit as st

from src.components.common import section_header
from src.components.timer import render_focus_timer
from src.html_utils import render_html


def render():
    section_header(
        "Focus timer",
        "Protect one honest block of attention",
        "Start it here and it keeps running in the sidebar as you move around "
        "the app.",
    )

    timer_col, intention_col = st.columns([1.5, 1], gap="large")

    with timer_col:
        with st.container(border=True):
            st.slider(
                "Session length (minutes)",
                min_value=5,
                max_value=60,
                step=5,
                value=25,
                key="timer_length",
            )
            st.caption(
                "Pick a length, then press Start. Changing the length resets a "
                "timer that hasn't started yet."
            )
            render_focus_timer(st.session_state.timer_length)

    with intention_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Set an intention</div>
                <div class="card-subtitle">
                    A clear aim makes a focus block far easier to keep
                </div>
                """
            )

            st.selectbox(
                "What are you focusing on?",
                [
                    "Adaptive practice",
                    "Reviewing mistakes",
                    "A timed module",
                    "Learning a new skill",
                    "Light review",
                ],
                index=0,
                key="focus_activity",
            )

            st.text_area(
                "One sentence on what 'done' looks like",
                value="",
                height=90,
                key="session_intention",
                placeholder="e.g. Finish 10 algebra questions and log every miss.",
            )

            st.toggle(
                "Distraction-free reminder",
                value=False,
                key="distraction_mode",
                help="A gentle nudge to close everything you don't need.",
            )

            if st.session_state.get("distraction_mode"):
                st.caption(
                    "Close every tab except this one. You can reopen the world in "
                    f"{st.session_state.timer_length} minutes."
                )

        st.write("")
        render_html(
            """
            <div class="coach-quote">
                One unbroken block of focus beats an afternoon of half-attention.
            </div>
            """
        )
