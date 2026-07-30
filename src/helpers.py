"""Small presentation helpers shared across views.

These read session state and format it for display: countdowns, the greeting,
overall accuracy, relative timestamps, and the prep-window progress bar.
"""

from datetime import date, datetime

import streamlit as st


def days_until_sat() -> int:
    return max((st.session_state.sat_date - date.today()).days, 0)


def format_sat_date() -> str:
    d = st.session_state.sat_date
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def prep_window_percent(window_days: int = 180) -> int:
    elapsed = window_days - days_until_sat()
    return max(0, min(round(elapsed / window_days * 100), 100))


def accuracy() -> int:
    if st.session_state.questions_solved == 0:
        return 0
    return round(
        st.session_state.correct_answers
        / st.session_state.questions_solved
        * 100
    )


def greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"


def status_for_accuracy(value):
    if value >= 80:
        return "Strong"
    if value >= 65:
        return "Developing"
    return "Needs work"


def relative_time(ts):
    seconds = (datetime.now() - ts).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    return f"{int(seconds // 86400)} d ago"
