"""Metrics derived from the answer history.

These functions read ``st.session_state.history`` and turn it into the numbers
the dashboard shows: accuracy, per-skill stats, a predicted score, and streaks.
``recompute_metrics`` runs once per script rerun to refresh the cached values.
"""

from datetime import date, timedelta

import streamlit as st


def skill_stats(history):
    stats = {}
    for entry in history:
        record = stats.setdefault(
            entry["skill"],
            {"n": 0, "c": 0, "section": entry["section"], "domain": entry["domain"]},
        )
        record["n"] += 1
        record["c"] += 1 if entry["correct"] else 0
    for record in stats.values():
        record["acc"] = round(record["c"] / record["n"] * 100) if record["n"] else 0
    return stats


def weakest_skills(history):
    stats = skill_stats(history)
    ranked = sorted(stats.items(), key=lambda kv: (kv[1]["acc"], -kv[1]["n"]))
    return [skill for skill, _ in ranked]


def _section_scaled(history, section):
    entries = [e for e in history if e["section"] == section]
    if not entries:
        return None
    accuracy_fraction = sum(1 for e in entries if e["correct"]) / len(entries)
    # Each SAT section runs 200-800 in ten-point increments.
    return int(round((200 + accuracy_fraction * 600) / 10) * 10)


def predicted_score(history):
    if not history:
        return 0
    math_score = _section_scaled(history, "math")
    rw_score = _section_scaled(history, "reading_writing")
    if math_score is None and rw_score is None:
        return 0
    # If a section has no data yet, assume it mirrors the other.
    if math_score is None:
        math_score = rw_score
    if rw_score is None:
        rw_score = math_score
    return math_score + rw_score


def compute_streak(history):
    days = {entry["ts"].date() for entry in history}
    if not days:
        return 0
    today = date.today()
    cursor = today if today in days else max(days)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def recompute_metrics():
    history = st.session_state.history
    today = date.today()

    solved = len(history)
    correct = sum(1 for e in history if e["correct"])
    total_seconds = sum(e["seconds"] for e in history)
    today_seconds = sum(e["seconds"] for e in history if e["ts"].date() == today)

    st.session_state.questions_solved = solved
    st.session_state.correct_answers = correct
    st.session_state.study_minutes = int(round(total_seconds / 60))
    st.session_state.today_minutes = int(round(today_seconds / 60))
    st.session_state.questions_mastered = correct
    st.session_state.predicted_score = predicted_score(history)
    st.session_state.streak = compute_streak(history)
    st.session_state.best_streak = max(
        st.session_state.get("best_streak", 0),
        st.session_state.streak,
    )
