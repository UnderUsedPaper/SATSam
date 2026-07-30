"""Application-wide constants.

Everything here is a plain value or lookup table with no Streamlit side effects,
so it is safe to import from anywhere without worrying about ordering.
"""

from datetime import date

# ------------------------------------------------------------------
# Navigation
# ------------------------------------------------------------------

PAGES = [
    "Home",
    "Practice",
    "Insights",
    "Study Plan",
    "Focus Timer",
    "Settings",
]


# ------------------------------------------------------------------
# Difficulty
# ------------------------------------------------------------------

DIFFICULTY_ORDER = ["easy", "medium", "hard"]

# Maps the four-step "Starting difficulty" slider onto the three difficulty
# tiers that actually exist in the question bank.
START_DIFFICULTY = {
    "Foundation": "easy",
    "Standard": "medium",
    "Challenging": "hard",
    "Test-level": "hard",
}


# ------------------------------------------------------------------
# Settings persistence
# ------------------------------------------------------------------

PERSISTED_KEYS = [
    "study_goal",
    "target_score",
    "sat_date",
    "default_practice_subject",
    "default_start_difficulty",
    "default_practice_count",
    "auto_explain",
    "show_timing",
    "ai_enabled",
    "ai_host",
    "ai_model",
    "ai_temperature",
    "explanation_style",
    "coach_personality",
    "study_circumstances",
    "ai_study_plan",
]


# ------------------------------------------------------------------
# AI coach voice
# ------------------------------------------------------------------

COACH_STYLE_GUIDANCE = {
    "Concise and strategic": "Explain in two or three tight sentences focused on the fastest reliable path to the answer.",
    "Step-by-step": "Walk through the solution one clear, numbered step at a time.",
    "Socratic questions": "Guide with leading questions that help the student reach the answer themselves before confirming it.",
    "Detailed tutor mode": "Give a thorough explanation covering the underlying concept, the full solution, and one common trap.",
}

COACH_PERSONALITY_GUIDANCE = {
    "Warm and focused": "Be encouraging and supportive while staying on task.",
    "Direct and challenging": "Be blunt and push the student to think harder; skip the padding.",
    "Calm and encouraging": "Be patient, reassuring, and low-pressure.",
}


# ------------------------------------------------------------------
# Study plan
# ------------------------------------------------------------------

PLAN_DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

OFFICIAL_MODULE_MINUTES = {
    "reading_writing": 32,
    "math": 35,
}


# ------------------------------------------------------------------
# Error Fingerprint vocabulary
# ------------------------------------------------------------------

ERROR_TYPE_LABELS = {
    "concept_gap": "Concept gap",
    "misread_question": "Misread the question",
    "wrong_strategy": "Wrong strategy",
    "execution_error": "Execution error",
    "tempting_distractor": "Tempting distractor",
    "overthinking": "Overthinking",
    "rushed_answer": "Rushed answer",
    "guessing": "Likely guess",
    "time_management": "Time-management issue",
    "careless_error": "Careless error",
    "unknown": "Unclear pattern",
}

ERROR_TYPE_ICONS = {
    "concept_gap": "◇",
    "misread_question": "◉",
    "wrong_strategy": "↗",
    "execution_error": "±",
    "tempting_distractor": "◎",
    "overthinking": "∞",
    "rushed_answer": "⚡",
    "guessing": "?",
    "time_management": "◷",
    "careless_error": "!",
    "unknown": "✦",
}

ERROR_TYPE_COLORS = {
    "concept_gap": "#9B6A58",
    "misread_question": "#A87557",
    "wrong_strategy": "#B7864B",
    "execution_error": "#B45F4C",
    "tempting_distractor": "#B76E5B",
    "overthinking": "#8E7468",
    "rushed_answer": "#C17A50",
    "guessing": "#8A8075",
    "time_management": "#7F8C72",
    "careless_error": "#B28B52",
    "unknown": "#8A8075",
}


# ------------------------------------------------------------------
# Session state defaults
# ------------------------------------------------------------------

DEFAULT_STATE = {
    # User-set targets (some are bound to widgets).
    "study_goal": 45,
    "target_score": 1500,
    "sat_date": date(2026, 9, 6),
    "page": "Home",

    # Practice session state.
    "practice_phase": "setup",          # setup | question | summary | empty
    "answer_submitted": False,
    "current_q": None,
    "current_difficulty": "medium",
    "session_config": None,
    "session_used_ids": set(),
    "session_answered": 0,
    "session_correct": 0,
    "session_seconds": 0.0,
    "session_last_answer": None,
    "session_last_correct": None,
    "question_start": 0.0,

    # Persistent progress log.
    "history": [],
    "score_history": [],
    "sessions_completed": 0,
    "best_streak": 0,

    # Derived metrics (refreshed every run by recompute_metrics).
    "questions_solved": 0,
    "correct_answers": 0,
    "study_minutes": 0,
    "today_minutes": 0,
    "predicted_score": 0,
    "questions_mastered": 0,
    "streak": 0,

    # Session defaults (pre-fill the Practice setup).
    "default_practice_subject": "SATSam recommendation",
    "default_start_difficulty": "Standard",
    "default_practice_count": 12,
    "auto_explain": True,
    "show_timing": True,

    # AI tutor (local Ollama model).
    "ai_enabled": True,
    "ai_host": "http://localhost:11434",
    "ai_model": "qwen3:8b",
    "ai_temperature": 0.7,
    "explanation_style": "Concise and strategic",
    "coach_personality": "Warm and focused",

    # Personal circumstances that make studying harder (feeds the planner).
    "study_circumstances": "",

    # Free-form "Chat with Sam" conversation state (session only).
    "chat_open": False,
    "chat_messages": [],
    "chat_context": None,
    "chat_pending": None,

    # The most recent AI-generated study plan (persisted to settings).
    "ai_study_plan": None,

    # Skills the AI chose to target for the current session (runtime only).
    "ai_focus_skills": [],
    "error_fingerprint_cache": {},

    # Misc.
    "pomodoro_running": False,
}
