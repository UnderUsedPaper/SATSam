"""Feature 1: coach-style answer explanations grounded in the reference answer."""

import streamlit as st

from src.ai.client import ollama_chat
from src.ai.prompts import build_coach_system_prompt, question_for_prompt


def ai_explain_answer(question, user_answer, is_correct):
    """Coach-style explanation grounded in the question's reference answer."""
    if is_correct:
        task = (
            "The student answered CORRECTLY. In two or three sentences, celebrate "
            "that and reinforce the key idea or shortcut worth remembering. Do not "
            "simply repeat the reference explanation word for word."
        )
    else:
        task = (
            f"The student answered INCORRECTLY, choosing '{user_answer}'. Warmly and "
            "briefly name the most likely misstep behind that choice, then walk them "
            "to the correct answer with clear, reassuring reasoning."
        )

    user_prompt = (
        f"{question_for_prompt(question)}\n\n"
        f"Student's answer: {user_answer}\n\n"
        f"{task} Treat the reference explanation as the source of truth for the "
        "underlying math or logic, and speak warmly and directly to the student, as "
        "if you're sitting beside them and glad to help. Do not use Markdown headers; "
        "keep it to a short, encouraging paragraph."
    )
    return ollama_chat(build_coach_system_prompt(), user_prompt)


def get_ai_explanation(question, user_answer, is_correct):
    """Cache explanations per answer so Streamlit reruns don't re-query the model."""
    cache = st.session_state.setdefault("ai_explanations", {})
    key = f"{question['id']}::{user_answer}"
    if key not in cache:
        cache[key] = ai_explain_answer(question, user_answer, is_correct)
    return cache[key]
