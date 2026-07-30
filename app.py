"""SATSam — application entry point.

Run with:  streamlit run app.py

Order matters here. ``st.set_page_config`` must be the very first Streamlit
command, so it runs before any ``src`` module is imported. Everything else is
wired up as a short, readable sequence: seed state, refresh metrics, inject the
stylesheet, draw the sidebar (which decides the current page), mount the chat
launcher, and route to the selected view.
"""

import streamlit as st

st.set_page_config(
    page_title="SATSam — Your Personal SAT Coach",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Imported only after set_page_config so nothing fires a Streamlit command early.
from src.components.chat import render_floating_chat          # noqa: E402
from src.components.sidebar import render_sidebar             # noqa: E402
from src.metrics import recompute_metrics                     # noqa: E402
from src.state import init_state                              # noqa: E402
from src.styles import inject_global_styles                   # noqa: E402
from src.views import (                                       # noqa: E402
    focus_timer,
    home,
    insights,
    practice,
    settings as settings_view,
    study_plan,
)

PAGE_RENDERERS = {
    "Home": home.render,
    "Practice": practice.render,
    "Insights": insights.render,
    "Study Plan": study_plan.render,
    "Focus Timer": focus_timer.render,
    "Settings": settings_view.render,
}


def main():
    init_state()
    recompute_metrics()
    inject_global_styles()

    page = render_sidebar()
    render_floating_chat()

    renderer = PAGE_RENDERERS.get(page, home.render)
    renderer()


main()
