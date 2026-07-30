"""Feature 2: the AI Error Fingerprint.

Instead of only explaining the correct answer, this asks the local model to
name the most likely *reasoning behavior* behind a wrong answer (a concept gap,
a misread, a rushed guess, and so on), with a graceful heuristic fallback when
the model is unavailable.
"""

import json
from datetime import datetime

import streamlit as st

from src.ai.client import ollama_chat, parse_json_response
from src.ai.prompts import question_for_prompt
from src.config import ERROR_TYPE_COLORS, ERROR_TYPE_ICONS, ERROR_TYPE_LABELS
from src.html_utils import esc, render_html, to_html_block


def normalize_fingerprint(data, question, user_answer, elapsed_seconds):
    """
    Validate the model's JSON and guarantee that the UI always receives
    a complete, safe fingerprint dictionary.
    """
    allowed_error_types = set(ERROR_TYPE_LABELS)

    if not isinstance(data, dict):
        data = {}

    error_type = str(data.get("error_type", "unknown")).strip().lower()
    if error_type not in allowed_error_types:
        error_type = "unknown"

    try:
        confidence = float(data.get("confidence", 0.65))
    except (TypeError, ValueError):
        confidence = 0.65

    # Accept either 0-1 or 0-100 from the model.
    if confidence > 1:
        confidence = confidence / 100

    confidence = max(0.0, min(confidence, 1.0))

    root_cause = str(
        data.get(
            "root_cause",
            "The selected answer does not follow the question's required reasoning.",
        )
    ).strip()

    evidence = str(
        data.get(
            "evidence",
            "The answer differs from the correct response.",
        )
    ).strip()

    micro_skill = str(
        data.get("micro_skill", question.get("skill", "SAT reasoning"))
    ).strip()

    strategy = str(
        data.get(
            "recommended_strategy",
            "Slow down, identify exactly what the question asks, and verify each step.",
        )
    ).strip()

    next_step = str(
        data.get(
            "next_step",
            f"Practice another {question.get('skill', 'similar')} question.",
        )
    ).strip()

    student_pattern = str(
        data.get(
            "student_pattern",
            "This may be an isolated mistake. Sam will compare it with future answers.",
        )
    ).strip()

    return {
        "error_type": error_type,
        "error_label": ERROR_TYPE_LABELS[error_type],
        "icon": ERROR_TYPE_ICONS[error_type],
        "color": ERROR_TYPE_COLORS[error_type],
        "root_cause": root_cause,
        "evidence": evidence,
        "micro_skill": micro_skill,
        "recommended_strategy": strategy,
        "next_step": next_step,
        "student_pattern": student_pattern,
        "confidence": confidence,
        "confidence_percent": round(confidence * 100),
        "question_id": question.get("id"),
        "skill": question.get("skill"),
        "student_answer": str(user_answer),
        "correct_answer": str(question.get("correct")),
        "elapsed_seconds": round(float(elapsed_seconds), 1),
        "created_at": datetime.now(),
        "source": "ai",
    }


def fallback_error_fingerprint(question, user_answer, elapsed_seconds):
    """
    Create a useful diagnosis when Ollama is unavailable or its response
    cannot be parsed. This keeps the app functional during a live demo.
    """
    estimated = question.get("estimated_seconds") or 0
    distractor_note = question.get("distractors", {}).get(user_answer, "")

    if estimated and elapsed_seconds < estimated * 0.35:
        error_type = "rushed_answer"
        root_cause = (
            "You answered much faster than the suggested time, so it's worth "
            "checking whether the question or answer choices got a full read."
        )
        evidence = (
            f"You answered in {round(elapsed_seconds)} seconds while this question "
            f"was estimated to take about {estimated} seconds."
        )
        strategy = (
            "Before submitting, restate what the question asks and eliminate "
            "at least two answer choices."
        )

    elif estimated and elapsed_seconds > estimated * 1.8:
        error_type = "overthinking"
        root_cause = (
            "You may have taken a longer or more complicated route than this "
            "question needed."
        )
        evidence = (
            f"You spent {round(elapsed_seconds)} seconds on a question estimated "
            f"at about {estimated} seconds."
        )
        strategy = (
            "Look for the tested rule or relationship before beginning a "
            "full calculation."
        )

    elif distractor_note:
        error_type = "tempting_distractor"
        root_cause = distractor_note
        evidence = (
            "The option you chose matches a known distractor pattern stored "
            "with this question."
        )
        strategy = (
            "Compare every answer choice against the exact wording and evidence "
            "in the question."
        )

    else:
        error_type = "concept_gap"
        root_cause = (
            f"Your answer suggests the idea behind "
            f"{question.get('skill', 'the tested concept')} isn't fully settled yet."
        )
        evidence = (
            f"You entered {user_answer}, while the supported answer is "
            f"{question.get('correct')}."
        )
        strategy = (
            "Review the core rule, then solve a similar question while explaining "
            "each step aloud."
        )

    fingerprint = {
        "error_type": error_type,
        "root_cause": root_cause,
        "evidence": evidence,
        "micro_skill": question.get("skill", "SAT reasoning"),
        "recommended_strategy": strategy,
        "next_step": (
            f"Complete one recovery question on "
            f"{question.get('skill', 'this skill')}."
        ),
        "student_pattern": (
            "Sam needs a few more attempts to tell whether this is a recurring pattern."
        ),
        "confidence": 0.62,
    }

    normalized = normalize_fingerprint(
        fingerprint,
        question,
        user_answer,
        elapsed_seconds,
    )
    normalized["source"] = "fallback"
    return normalized


def recent_error_context(limit=8):
    """
    Give the AI a small amount of prior mistake history so it can distinguish
    a one-time error from a repeated reasoning pattern.
    """
    prior_errors = []

    for entry in reversed(st.session_state.get("history", [])):
        fingerprint = entry.get("fingerprint")

        if entry.get("correct") or not fingerprint:
            continue

        prior_errors.append(
            {
                "skill": entry.get("skill"),
                "error_type": fingerprint.get("error_type"),
                "root_cause": fingerprint.get("root_cause"),
            }
        )

        if len(prior_errors) >= limit:
            break

    return prior_errors


def ai_error_fingerprint(question, user_answer, elapsed_seconds):
    """
    Ask the local model to identify the most likely cognitive reason behind
    an incorrect response. Returns (success, fingerprint_or_error).
    """
    prior_context = recent_error_context()

    if question.get("format") == "mcq":
        selected_choice_text = next(
            (
                choice.get("text", "")
                for choice in question.get("choices", [])
                if choice.get("id") == user_answer
            ),
            "",
        )
    else:
        selected_choice_text = str(user_answer)

    distractor_note = question.get("distractors", {}).get(user_answer, "")
    estimated_seconds = question.get("estimated_seconds") or 0

    system_prompt = """
You are Sam's cognitive-diagnosis engine, and you care about this student.

Your job is not merely to explain the correct answer. Identify the most likely
reasoning behavior that caused the student's incorrect answer.

Stay grounded in the question, the reference explanation, the selected answer,
any known distractor rationale, the response time, and the student's recent
error history.

Choose exactly one error_type from:
- concept_gap
- misread_question
- wrong_strategy
- execution_error
- tempting_distractor
- overthinking
- rushed_answer
- guessing
- time_management
- careless_error
- unknown

Write the human-facing text warmly and directly to the student ("you"), never
clinically. Do not claim certainty about their mental state; use cautious,
gentle language such as "likely," "may have," or "suggests."

Return only valid JSON. Do not use Markdown or add text outside the JSON.
""".strip()

    user_prompt = f"""
QUESTION INFORMATION
{question_for_prompt(question)}

STUDENT RESPONSE
Selected answer: {user_answer}
Selected answer text: {selected_choice_text or "Not available"}
Correct answer: {question.get("correct")}
Time used: {round(float(elapsed_seconds), 1)} seconds
Suggested time: {estimated_seconds or "Not available"} seconds
Known distractor rationale: {distractor_note or "None provided"}

RECENT DIAGNOSED ERRORS
{json.dumps(prior_context, indent=2, default=str)}

Return this exact JSON structure:
{{
  "error_type": "one allowed error type",
  "root_cause": "one or two warm sentences describing the likely underlying mistake",
  "evidence": "specific evidence from the student's answer, timing, or distractor",
  "micro_skill": "the narrow skill to strengthen",
  "recommended_strategy": "one concrete strategy usable on a future SAT question",
  "next_step": "one immediate, doable recovery action",
  "student_pattern": "state whether this resembles a prior pattern or may be isolated",
  "confidence": 0.0
}}

Confidence must be between 0 and 1.

Do not merely say that the answer was wrong. Diagnose the reasoning behavior
that most likely produced it, and speak to the student kindly.
""".strip()

    ok, text = ollama_chat(
        system_prompt,
        user_prompt,
        temperature=0.2,
        force_json=True,
    )

    if not ok:
        return False, text

    parsed = parse_json_response(text)

    if not isinstance(parsed, dict):
        return False, "The model did not return a valid diagnosis."

    fingerprint = normalize_fingerprint(
        parsed,
        question,
        user_answer,
        elapsed_seconds,
    )

    return True, fingerprint


def get_error_fingerprint(question, user_answer, elapsed_seconds):
    """
    Generate the fingerprint only once for each recorded attempt and store it
    inside the matching history entry.
    """
    history = st.session_state.get("history", [])
    attempt_number = len(history)

    cache = st.session_state.setdefault("error_fingerprint_cache", {})
    cache_key = f"{question['id']}::{user_answer}::{attempt_number}"

    if cache_key not in cache:
        ok, result = ai_error_fingerprint(
            question,
            user_answer,
            elapsed_seconds,
        )

        if ok:
            cache[cache_key] = result
        else:
            cache[cache_key] = fallback_error_fingerprint(
                question,
                user_answer,
                elapsed_seconds,
            )

    fingerprint = cache[cache_key]

    # Save the diagnosis into the newest matching history record.
    if history:
        latest_entry = history[-1]

        if (
            latest_entry.get("id") == question.get("id")
            and not latest_entry.get("correct")
        ):
            latest_entry["fingerprint"] = fingerprint

    return fingerprint


def render_error_fingerprint(fingerprint):
    """
    Render the AI Error Fingerprint using SATSam's warm, cozy visual theme.
    """
    if not fingerprint:
        return

    accent = fingerprint.get("color", "#B76E5B")
    icon = esc(fingerprint.get("icon", "✦"))
    label = esc(fingerprint.get("error_label", "Error pattern"))
    confidence = int(fingerprint.get("confidence_percent", 0))

    source_note = (
        "AI cognitive diagnosis"
        if fingerprint.get("source") == "ai"
        else "SATSam backup diagnosis"
    )

    root_cause = to_html_block(fingerprint.get("root_cause", ""))
    evidence = to_html_block(fingerprint.get("evidence", ""))
    micro_skill = esc(fingerprint.get("micro_skill", ""))
    strategy = to_html_block(fingerprint.get("recommended_strategy", ""))
    student_pattern = to_html_block(fingerprint.get("student_pattern", ""))
    next_step = esc(fingerprint.get("next_step", ""))

    render_html(
        f"""
        <div style="
            margin-top: 22px;
            margin-bottom: 20px;
            padding: 24px;
            border-radius: 20px;
            border: 1px solid #D8CCBC;
            border-left: 5px solid {accent};
            background:
                radial-gradient(circle at top right, {accent}18, transparent 42%),
                linear-gradient(145deg, #FBF7EF 0%, #F7F0E5 100%);
            box-shadow: 0 12px 28px rgba(76, 57, 41, 0.08), 0 2px 7px rgba(76, 57, 41, 0.05);
        ">
            <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 13px;">
                    <div style="
                        width: 46px; height: 46px; flex: 0 0 46px;
                        display: flex; align-items: center; justify-content: center;
                        border-radius: 14px; background: {accent}; color: #FFFDF8;
                        font-size: 21px; font-weight: 750; box-shadow: 0 5px 12px {accent}30;
                    ">{icon}</div>
                    <div>
                        <div style="margin-bottom: 4px; color: #9A6A56; font-size: 10px; font-weight: 850; letter-spacing: 0.14em; text-transform: uppercase;">
                            Sam's Error Fingerprint
                        </div>
                        <div style="color: #34261F; font-family: Georgia, 'Times New Roman', serif; font-size: 22px; line-height: 1.2; font-weight: 700;">
                            {label}
                        </div>
                    </div>
                </div>
                <div style="padding: 7px 11px; border-radius: 999px; border: 1px solid {accent}55; background: {accent}14; color: #6F4B3D; font-size: 11px; font-weight: 750; white-space: nowrap;">
                    {confidence}% confidence
                </div>
            </div>
            <div style="height: 7px; overflow: hidden; margin-bottom: 20px; border-radius: 999px; background: #E8DED1;">
                <div style="width: {confidence}%; height: 100%; border-radius: 999px; background: linear-gradient(90deg, {accent}, #C99374);"></div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px;">
                <div style="padding: 16px; border-radius: 15px; border: 1px solid #DDD1C2; background: rgba(255, 253, 248, 0.82);">
                    <div style="margin-bottom: 7px; color: #A06F58; font-size: 10px; font-weight: 850; letter-spacing: 0.11em; text-transform: uppercase;">Likely root cause</div>
                    <div style="color: #4A3930; font-size: 13px; line-height: 1.62;">{root_cause}</div>
                </div>
                <div style="padding: 16px; border-radius: 15px; border: 1px solid #DDD1C2; background: rgba(255, 253, 248, 0.82);">
                    <div style="margin-bottom: 7px; color: #A06F58; font-size: 10px; font-weight: 850; letter-spacing: 0.11em; text-transform: uppercase;">Evidence Sam noticed</div>
                    <div style="color: #4A3930; font-size: 13px; line-height: 1.62;">{evidence}</div>
                </div>
                <div style="padding: 16px; border-radius: 15px; border: 1px solid #D5D8C8; background: #F2F3E9;">
                    <div style="margin-bottom: 7px; color: #788069; font-size: 10px; font-weight: 850; letter-spacing: 0.11em; text-transform: uppercase;">Micro-skill to strengthen</div>
                    <div style="color: #3F4538; font-size: 13px; line-height: 1.55; font-weight: 750;">{micro_skill}</div>
                </div>
                <div style="padding: 16px; border-radius: 15px; border: 1px solid #DDD1C2; background: #FFF9EF;">
                    <div style="margin-bottom: 7px; color: #A06F58; font-size: 10px; font-weight: 850; letter-spacing: 0.11em; text-transform: uppercase;">Use this strategy</div>
                    <div style="color: #4A3930; font-size: 13px; line-height: 1.62;">{strategy}</div>
                </div>
            </div>
            <div style="margin-top: 13px; padding: 15px 16px; border-radius: 15px; border: 1px solid {accent}3D; background: {accent}10;">
                <div style="margin-bottom: 6px; color: {accent}; font-size: 10px; font-weight: 850; letter-spacing: 0.11em; text-transform: uppercase;">Pattern intelligence</div>
                <div style="color: #4A3930; font-size: 13px; line-height: 1.6;">{student_pattern}</div>
            </div>
            <div style="display: flex; align-items: flex-start; gap: 9px; margin-top: 15px; padding: 13px 15px; border-radius: 14px; border: 1px solid #E1D4B5; background: #FBF1D2;">
                <div style="color: #A46F39; font-size: 12px; line-height: 1.55; font-weight: 850; white-space: nowrap;">Next:</div>
                <div style="color: #58452F; font-size: 12px; line-height: 1.55;">{next_step}</div>
            </div>
            <div style="margin-top: 13px; color: #A39586; font-size: 9px; letter-spacing: 0.09em; line-height: 1.5; text-transform: uppercase;">
                {esc(source_note)} · Diagnosis describes a likely pattern, not certainty
            </div>
        </div>
        """
    )
