"""The left sidebar: brand, navigation, quick stats, mini timer, quick start."""

import streamlit as st

from src.components.timer import render_mini_timer
from src.config import PAGES
from src.helpers import days_until_sat, format_sat_date, prep_window_percent
from src.html_utils import render_html
from src.state import go_to, quick_session_config, start_session


def render_sidebar():
    """Draw the sidebar and return the currently selected page."""
    with st.sidebar:
        render_html(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-row">
                    <div class="brand-mark">S</div>
                    <div>
                        <div class="brand-name">SATSam</div>
                        <div class="brand-caption">Thoughtful SAT preparation</div>
                    </div>
                </div>
            </div>
            """
        )

        render_html('<div class="sidebar-label">Workspace</div>')

        page = st.radio(
            "Navigation",
            PAGES,
            key="page",
            label_visibility="collapsed",
        )

        if st.button("💬  Chat with Sam", use_container_width=True,
                     key="open_chat_sidebar"):
            st.session_state.chat_open = True
            st.rerun()

        render_html(
            f"""
            <div class="sidebar-card">
                <div class="sidebar-card-label">Next SAT</div>
                <div class="sidebar-card-value">{format_sat_date()}</div>
                <div class="sidebar-card-detail">{days_until_sat()} days remaining</div>
                <div class="mini-progress">
                    <div class="mini-progress-fill" style="width: {prep_window_percent()}%;"></div>
                </div>
            </div>
            <div class="sidebar-card">
                <div class="sidebar-card-label">Current streak</div>
                <div class="sidebar-card-value">{st.session_state.streak} focused days</div>
                <div class="sidebar-card-detail">Your best streak is {st.session_state.best_streak} days</div>
            </div>
            """
        )

        if page != "Focus Timer":
            render_html('<div class="sidebar-label">Focus timer</div>')
            render_mini_timer()

        st.write("")

        if st.button(
            "Start quick practice",
            type="primary",
            use_container_width=True,
        ):
            start_session(quick_session_config())
            go_to("Practice")

    return page
