"""Session-state setup and the practice-session lifecycle.

``init_state`` seeds ``st.session_state`` from the defaults (and any saved
settings), pre-fills the Practice widgets, and applies a pending navigation
request. It must run before the sidebar radio is created.
"""

import time

import streamlit as st

from src.ai.coaching import ai_recommend_focus_skills
from src.config import DEFAULT_STATE, START_DIFFICULTY
from src.metrics import predicted_score
from src.questions import pick_next
from src.settings_store import load_settings


def init_state():
    """Seed session state, pre-fill widgets, and apply pending navigation."""
    saved_settings = load_settings()
    for key, value in DEFAULT_STATE.items():
        if key in saved_settings:
            value = saved_settings[key]
        if key not in st.session_state:
            st.session_state[key] = value

    # Pre-fill the Practice setup widgets from the saved session defaults.
    for widget_key, default_value in {
        "practice_subject": st.session_state.default_practice_subject,
        "practice_focus": "Highest-impact weakness",
        "practice_difficulty": st.session_state.default_start_difficulty,
        "practice_questions": st.session_state.default_practice_count,
        "practice_explanations": st.session_state.auto_explain,
    }.items():
        if widget_key not in st.session_state:
            st.session_state[widget_key] = default_value

    # Navigation requested by a button on the previous run. This has to be
    # applied *before* the sidebar radio is created.
    if "pending_page" in st.session_state:
        st.session_state.page = st.session_state.pop("pending_page")


def go_to(page_name: str) -> None:
    st.session_state.pending_page = page_name
    st.rerun()


def start_session(config):
    """Build a fresh adaptive practice session from a config dict."""
    st.session_state.session_config = config
    st.session_state.session_used_ids = set()
    st.session_state.session_answered = 0
    st.session_state.session_correct = 0
    st.session_state.session_seconds = 0.0
    st.session_state.current_difficulty = config["start_difficulty"]
    st.session_state.answer_submitted = False
    st.session_state.session_last_answer = None
    st.session_state.session_last_correct = None

    # Let the model prioritize which weak skills to target this session.
    st.session_state.ai_focus_skills = []
    if (st.session_state.get("ai_enabled")
            and config["focus"] == "Highest-impact weakness"
            and st.session_state.history):
        with st.spinner("Sam is looking at where you can gain the most…"):
            st.session_state.ai_focus_skills = ai_recommend_focus_skills(
                st.session_state.history
            )

    question = pick_next(config, st.session_state.session_used_ids,
                         config["start_difficulty"])
    st.session_state.current_q = question
    st.session_state.question_start = time.time()
    st.session_state.practice_phase = "question" if question else "empty"


def finalize_session():
    st.session_state.score_history.append(
        predicted_score(st.session_state.history)
    )
    st.session_state.sessions_completed += 1
    st.session_state.practice_phase = "summary"


def quick_session_config():
    """A one-tap session that uses the user's saved defaults but always
    targets their weakest skills."""
    return {
        "subject": st.session_state.default_practice_subject,
        "focus": "Highest-impact weakness",
        "start_difficulty": START_DIFFICULTY.get(
            st.session_state.default_start_difficulty, "medium"
        ),
        "count": st.session_state.default_practice_count,
        "explain": st.session_state.auto_explain,
    }
