"""Loads the SAT question bank once and exposes it as ``QUESTIONS``.

The bank ships at ``data/sat-questions.json``. A couple of legacy fallbacks are
kept so older checkouts (where the file sat next to the app) still work.
"""

import json
import os

import streamlit as st

from src.paths import BASE_DIR, DATA_DIR, QUESTIONS_FILE


@st.cache_data(show_spinner=False)
def load_question_bank():
    candidates = [
        QUESTIONS_FILE,
        os.path.join(BASE_DIR, "sat-questions.json"),
        os.path.join(DATA_DIR, "questions.json"),
        "sat-questions.json",
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data.get("questions", [])
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return []


# Loaded once, when this module is first imported (which happens after
# st.set_page_config in app.py). Every module shares this single list.
QUESTIONS = load_question_bank()
