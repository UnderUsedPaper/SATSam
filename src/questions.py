"""Adaptive question selection and answer checking.

Given a session config and the set of already-used question IDs, ``pick_next``
chooses the next question, preferring the target difficulty and, in weakness
mode, the skills where accuracy is currently lowest.
"""

import random

import streamlit as st

from src.config import DIFFICULTY_ORDER
from src.data_loader import QUESTIONS
from src.metrics import weakest_skills


def subject_filter(question, subject) -> bool:
    if subject == "Math":
        return question["section"] == "math"
    if subject == "Reading and Writing":
        return question["section"] == "reading_writing"
    # "Balanced" and "SATSam recommendation" draw from everything.
    return True


def _focus_linear_equations(question) -> bool:
    skill = question["skill"].lower()
    return "linear equation" in skill or skill == "linear functions"


FOCUS_MATCHERS = {
    "Linear equations": _focus_linear_equations,
    "Problem solving and data": lambda q: q["domain"] == "Problem-Solving and Data Analysis",
    "Reading inference": lambda q: q["skill"] == "Inferences",
    "Grammar conventions": lambda q: q["domain"] == "Standard English Conventions",
}


def focus_filter(question, focus) -> bool:
    if focus == "Highest-impact weakness":
        return True
    matcher = FOCUS_MATCHERS.get(focus)
    return matcher(question) if matcher else True


def _candidate_pool(config, used_ids):
    return [
        q for q in QUESTIONS
        if q["id"] not in used_ids
        and subject_filter(q, config["subject"])
        and focus_filter(q, config["focus"])
    ]


def pick_next(config, used_ids, difficulty):
    """Choose the next question, preferring the target difficulty and,
    in weakness mode, the skills where accuracy is currently lowest."""
    pool = _candidate_pool(config, used_ids)
    if not pool:
        return None

    preferred = set()
    if config["focus"] == "Highest-impact weakness":
        # The AI (when enabled) chooses the priority skills at session start.
        # Otherwise fall back to the plain lowest-accuracy heuristic.
        ai_focus = st.session_state.get("ai_focus_skills") or []
        if ai_focus:
            preferred = set(ai_focus)
        else:
            preferred = set(weakest_skills(st.session_state.history)[:3])

    order = [difficulty] + [d for d in DIFFICULTY_ORDER if d != difficulty]
    for level in order:
        matches = [q for q in pool if q["difficulty"] == level]
        if not matches:
            continue
        if preferred:
            focused = [q for q in matches if q["skill"] in preferred]
            if focused:
                return random.choice(focused)
        return random.choice(matches)

    return random.choice(pool)


def shift_difficulty(difficulty, went_up):
    index = DIFFICULTY_ORDER.index(difficulty)
    index = min(index + 1, 2) if went_up else max(index - 1, 0)
    return DIFFICULTY_ORDER[index]


def spr_match(user_answer, correct) -> bool:
    text = (user_answer or "").strip()
    if not text:
        return False
    if text == str(correct).strip():
        return True
    try:
        return abs(float(text) - float(correct)) < 1e-6
    except ValueError:
        return False


def check_answer(question, user_answer) -> bool:
    if question["format"] == "mcq":
        return user_answer == question["correct"]
    return spr_match(user_answer, question["correct"])
