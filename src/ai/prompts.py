"""System prompts and prompt-formatting helpers for Sam, the AI tutor.

Kept separate from the client so the "voice" of the coach lives in one place
and the transport (Ollama calls) lives in another.
"""

import streamlit as st

from src.config import COACH_PERSONALITY_GUIDANCE, COACH_STYLE_GUIDANCE
from src.helpers import accuracy, days_until_sat
from src.metrics import weakest_skills


def build_coach_system_prompt():
    """Compose the system prompt sent to the local model, built from the
    explanation-style and coach-personality settings."""
    style = COACH_STYLE_GUIDANCE.get(
        st.session_state.get("explanation_style"),
        next(iter(COACH_STYLE_GUIDANCE.values())),
    )
    personality = COACH_PERSONALITY_GUIDANCE.get(
        st.session_state.get("coach_personality"),
        next(iter(COACH_PERSONALITY_GUIDANCE.values())),
    )
    return (
        "You are Sam, a warm and genuinely encouraging SAT coach who cares about "
        "the student you're helping. You speak to them directly and kindly, the way "
        "a patient mentor would sitting right beside them. "
        f"{personality} {style} "
        "Always address the student as \"you,\" never refer to them in the third "
        "person, and never sound like a system, a report, or a textbook. Keep every "
        "explanation accurate and specific to the question at hand, and end on a note "
        "that leaves them feeling capable of getting the next one."
    )


def question_for_prompt(question):
    """Flatten a question into plain text the model can reason over."""
    lines = [
        f"Skill: {question['skill']}",
        f"Domain: {question['domain']} | Difficulty: {question['difficulty']}",
    ]
    if question.get("stimulus"):
        lines.append(f"Passage/context: {question['stimulus']}")
    lines.append(f"Question: {question['prompt']}")
    if question["format"] == "mcq":
        for choice in question["choices"]:
            lines.append(f"  {choice['id']}. {choice['text']}")
        lines.append(f"Correct choice: {question['correct']}")
    else:
        lines.append(f"Correct answer: {question['correct']}")
    if question.get("explanation"):
        lines.append(f"Reference explanation: {question['explanation']}")
    return "\n".join(lines)


def build_chat_system_prompt():
    """System prompt for the free-form 'Chat with Sam' assistant. Warm, personal,
    and aware of the student's current goals and performance."""
    parts = [
        "You are Sam, a warm, encouraging, and knowledgeable SAT coach. You are "
        "chatting one-on-one with a student inside their study app. Talk to them "
        "like a kind human mentor: friendly, direct, specific, and clearly on their "
        "side. Use \"you,\" keep answers reasonably short and easy to read, and never "
        "sound like a system or a form.",
    ]

    # Personalize with whatever context we happen to have.
    try:
        target = st.session_state.get("target_score")
        days = days_until_sat()
        acc = accuracy()
        answered = st.session_state.get("questions_solved", 0)
        weak = weakest_skills(st.session_state.get("history", []))
        bits = []
        if target:
            bits.append(f"their target score is {target}")
        bits.append(f"their SAT is about {days} days away")
        if answered:
            bits.append(
                f"they've answered {answered} practice questions at {acc}% accuracy so far"
            )
        if weak:
            bits.append(
                "skills they're finding hardest right now include "
                + ", ".join(weak[:3])
            )
        circumstances = (st.session_state.get("study_circumstances") or "").strip()
        if circumstances:
            bits.append(
                "they've told you their life is harder than usual right now: "
                f"{circumstances}"
            )
        if bits:
            parts.append(
                "Here is what you know about this student: "
                + "; ".join(bits)
                + ". Use it to make your advice feel personal, but only raise it when "
                "it's relevant, and always stay kind and non-judgmental."
            )
    except Exception:
        pass

    # If the chat was opened from a specific missed question, ground Sam in it.
    context = st.session_state.get("chat_context")
    if isinstance(context, dict) and context.get("question"):
        q = context["question"]
        parts.append(
            "The student just got the following question wrong and wants to really "
            "understand it. Gently help them see where their thinking went sideways "
            "and how to get it right next time, without ever making them feel bad:\n"
            + question_for_prompt(q)
            + f"\nThe answer they chose was: {context.get('user_answer')}."
        )

    parts.append(
        "If they ask about something unrelated to the SAT, you can still be helpful "
        "and kind, but gently keep them oriented toward their goal."
    )
    return "\n\n".join(parts)
