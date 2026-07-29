import html as html_lib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
import streamlit.components.v1 as components
import ollama

import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="SATSam — Your Personal SAT Coach",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# HTML HELPERS
#
# Streamlit renders markdown first, HTML second. Any line that
# starts with four or more spaces becomes a fenced code block,
# and a blank line ends the raw-HTML block. Flattening every
# markup string to a single line removes both triggers.
# ============================================================

def flatten_html(markup: str) -> str:
    return " ".join(
        line.strip()
        for line in markup.splitlines()
        if line.strip()
    )


def render_html(markup: str) -> None:
    st.markdown(flatten_html(markup), unsafe_allow_html=True)


def esc(text) -> str:
    """Escape text for safe embedding inside raw HTML."""
    return html_lib.escape(str(text))


def to_html_block(text) -> str:
    """Escape and convert newlines to <br> so blocks survive flatten_html."""
    return esc(text).replace("\n", "<br>")


# ============================================================
# QUESTION BANK
#
# Loaded once from sat-questions.json, which must sit next to
# this file. Falls back to the working directory if needed.
# ============================================================

@st.cache_data(show_spinner=False)
def load_question_bank():
    candidates = []
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(here, "sat-questions.json"))
    except NameError:
        pass
    candidates.append("sat-questions.json")

    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data.get("questions", [])
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return []


QUESTIONS = load_question_bank()

DIFFICULTY_ORDER = ["easy", "medium", "hard"]

# Maps the four-step "Starting difficulty" slider onto the three
# difficulty tiers that actually exist in the question bank.
START_DIFFICULTY = {
    "Foundation": "easy",
    "Standard": "medium",
    "Challenging": "hard",
    "Test-level": "hard",
}


# ============================================================
# SETTINGS PERSISTENCE
#
# Preferences are saved to satsam-settings.json next to this
# file so they survive an app restart. Progress (answer
# history) intentionally stays in the session only.
# ============================================================

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
    "ai_hints",
    "ai_study_plan",
]


def settings_path():
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(here, "satsam-settings.json")
    except NameError:
        return "satsam-settings.json"


def load_settings():
    try:
        with open(settings_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if isinstance(data.get("sat_date"), str):
        try:
            data["sat_date"] = date.fromisoformat(data["sat_date"])
        except ValueError:
            data.pop("sat_date", None)
    return {k: v for k, v in data.items() if k in PERSISTED_KEYS}


def save_settings():
    data = {}
    for key in PERSISTED_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, date):
            value = value.isoformat()
        data[key] = value
    with open(settings_path(), "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


# ============================================================
# AI TUTOR (LOCAL OLLAMA MODEL)
#
# These helpers configure and probe a local model. The actual
# generation call is added alongside the Ollama integration;
# the settings below feed straight into it.
# ============================================================

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
        "You are Sam, a supportive SAT coach helping a student improve. "
        f"{personality} {style} "
        "Keep every explanation accurate and specific to the question at hand."
    )


def ollama_reachable(host, timeout=3):
    """Ping a local Ollama server's /api/tags endpoint.
    Returns (ok, models_list) on success or (False, error_message)."""
    url = host.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = [m.get("name", "") for m in payload.get("models", [])]
        return True, [m for m in models if m]
    except Exception as error:  # surface any failure to the user
        return False, str(error)


# ------------------------------------------------------------
# LOCAL MODEL CALLS
#
# All generation flows through ollama_chat, which talks to the
# local Ollama server configured in Settings. Every feature that
# uses the model degrades gracefully: if the server is
# unreachable or returns something unexpected, the app falls back
# to its built-in explanations and heuristics.
# ------------------------------------------------------------

_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think(text):
    """Remove qwen3-style <think> reasoning so only the answer remains."""
    if not text:
        return ""
    cleaned = _THINK_PATTERN.sub("", text)
    # A response may stream reasoning first and forget to close the tag, or
    # include only a closing tag right before the final answer.
    if "<think>" in cleaned and "</think>" not in cleaned:
        cleaned = cleaned.split("<think>")[0]
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1]
    return cleaned.strip()


def _extract_content(response):
    """Read message content from either dict-style or object-style responses,
    depending on the installed ollama version."""
    message = response["message"] if isinstance(response, dict) else response.message
    return message["content"] if isinstance(message, dict) else message.content


def _chat_with_optional_think(client, kwargs):
    """Call chat with thinking disabled when the installed Ollama supports it.
    qwen3 emits reasoning tokens by default; turning them off keeps tutoring
    responses fast. Older clients or non-thinking models fall back cleanly."""
    try:
        return client.chat(think=False, **kwargs)
    except TypeError:
        return client.chat(**kwargs)
    except Exception as error:
        if "think" in str(error).lower():
            return client.chat(**kwargs)
        raise


def ollama_chat(system_prompt, user_prompt, temperature=None, force_json=False):
    """Send a single system/user exchange to the local model.
    Returns (True, text) on success or (False, error_message)."""
    if temperature is None:
        temperature = st.session_state.get("ai_temperature", 0.7)

    kwargs = {
        "model": st.session_state.get("ai_model", "qwen3:8b"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {"temperature": float(temperature)},
    }
    if force_json:
        kwargs["format"] = "json"

    try:
        client = ollama.Client(
            host=(st.session_state.get("ai_host") or "http://localhost:11434")
        )
        response = _chat_with_optional_think(client, kwargs)
        return True, strip_think(_extract_content(response))
    except Exception as error:
        return False, str(error)


def parse_json_response(text):
    """Best-effort JSON parse of a model response, tolerating code fences and
    stray prose around the JSON payload."""
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost {...} or [...] block if extra text surrounds it.
    starts = [pos for pos in (cleaned.find("{"), cleaned.find("[")) if pos != -1]
    if not starts:
        return None
    start = min(starts)
    closer = "}" if cleaned[start] == "{" else "]"
    end = cleaned.rfind(closer)
    if end <= start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None


# ---- Feature 1: answer explanations -------------------------------------

def _question_for_prompt(question):
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


def ai_explain_answer(question, user_answer, is_correct):
    """Coach-style explanation grounded in the question's reference answer."""
    if is_correct:
        task = (
            "The student answered CORRECTLY. In two or three sentences, confirm "
            "why the answer is right and reinforce the key idea or shortcut worth "
            "remembering. Do not simply repeat the reference explanation word for "
            "word."
        )
    else:
        task = (
            f"The student answered INCORRECTLY, choosing '{user_answer}'. Briefly "
            "diagnose the most likely misstep behind that choice, then guide the "
            "student to the correct answer with clear reasoning. Stay encouraging."
        )

    user_prompt = (
        f"{_question_for_prompt(question)}\n\n"
        f"Student's answer: {user_answer}\n\n"
        f"{task} Treat the reference explanation as the source of truth for the "
        "underlying math or logic, and address the student directly. Do not use "
        "Markdown headers; keep it to a short paragraph."
    )
    return ollama_chat(build_coach_system_prompt(), user_prompt)


def get_ai_explanation(question, user_answer, is_correct):
    """Cache explanations per answer so Streamlit reruns don't re-query the model."""
    cache = st.session_state.setdefault("ai_explanations", {})
    key = f"{question['id']}::{user_answer}"
    if key not in cache:
        cache[key] = ai_explain_answer(question, user_answer, is_correct)
    return cache[key]


# ---- Feature 2: AI Error Fingerprint ------------------------------------

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
            "This may be an isolated mistake. SATSam will compare it with future answers.",
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
            "The response was submitted much faster than the suggested time, "
            "which may mean the question or answer choices were not fully checked."
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
            "You may have used a longer or more complicated approach than the "
            "question required."
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
            "The selected option matches a known distractor pattern stored "
            "with this question."
        )
        strategy = (
            "Compare every answer choice against the exact wording and evidence "
            "in the question."
        )

    else:
        error_type = "concept_gap"
        root_cause = (
            f"The response suggests an incomplete understanding of "
            f"{question.get('skill', 'the tested concept')}."
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
            "SATSam needs more attempts to determine whether this is a recurring pattern."
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
You are SATSam's cognitive-diagnosis engine.

Your job is not merely to explain the correct answer. Identify the most likely
reasoning behavior that caused the student's incorrect answer.

You must stay grounded in the question, the reference explanation, the selected
answer, any known distractor rationale, the response time, and the student's
recent error history.

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

Do not claim certainty about the student's mental state. Use cautious language
such as "likely," "may have," or "suggests."

Return only valid JSON. Do not use Markdown or add text outside the JSON.
""".strip()

    user_prompt = f"""
QUESTION INFORMATION
{_question_for_prompt(question)}

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
  "root_cause": "one or two sentences describing the likely underlying mistake",
  "evidence": "specific evidence from the student's answer, timing, or distractor",
  "micro_skill": "the narrow skill the student should improve",
  "recommended_strategy": "one concrete strategy usable on a future SAT question",
  "next_step": "one immediate recovery action",
  "student_pattern": "state whether this resembles a prior pattern or may be isolated",
  "confidence": 0.0
}}

Confidence must be between 0 and 1.

Do not merely say that the answer was wrong. Diagnose the reasoning behavior
that most likely produced it.
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

    root_cause = to_html_block(
        fingerprint.get("root_cause", "")
    )
    evidence = to_html_block(
        fingerprint.get("evidence", "")
    )
    micro_skill = esc(
        fingerprint.get("micro_skill", "")
    )
    strategy = to_html_block(
        fingerprint.get("recommended_strategy", "")
    )
    student_pattern = to_html_block(
        fingerprint.get("student_pattern", "")
    )
    next_step = esc(
        fingerprint.get("next_step", "")
    )

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
                radial-gradient(
                    circle at top right,
                    {accent}18,
                    transparent 42%
                ),
                linear-gradient(
                    145deg,
                    #FBF7EF 0%,
                    #F7F0E5 100%
                );
            box-shadow:
                0 12px 28px rgba(76, 57, 41, 0.08),
                0 2px 7px rgba(76, 57, 41, 0.05);
        ">

            <!-- Header -->
            <div style="
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 18px;
                margin-bottom: 20px;
            ">
                <div style="
                    display: flex;
                    align-items: center;
                    gap: 13px;
                ">
                    <div style="
                        width: 46px;
                        height: 46px;
                        flex: 0 0 46px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        border-radius: 14px;
                        background: {accent};
                        color: #FFFDF8;
                        font-size: 21px;
                        font-weight: 750;
                        box-shadow: 0 5px 12px {accent}30;
                    ">
                        {icon}
                    </div>

                    <div>
                        <div style="
                            margin-bottom: 4px;
                            color: #9A6A56;
                            font-size: 10px;
                            font-weight: 850;
                            letter-spacing: 0.14em;
                            text-transform: uppercase;
                        ">
                            Sam's Error Fingerprint
                        </div>

                        <div style="
                            color: #34261F;
                            font-family: Georgia, 'Times New Roman', serif;
                            font-size: 22px;
                            line-height: 1.2;
                            font-weight: 700;
                        ">
                            {label}
                        </div>
                    </div>
                </div>

                <div style="
                    padding: 7px 11px;
                    border-radius: 999px;
                    border: 1px solid {accent}55;
                    background: {accent}14;
                    color: #6F4B3D;
                    font-size: 11px;
                    font-weight: 750;
                    white-space: nowrap;
                ">
                    {confidence}% confidence
                </div>
            </div>

            <!-- Confidence bar -->
            <div style="
                height: 7px;
                overflow: hidden;
                margin-bottom: 20px;
                border-radius: 999px;
                background: #E8DED1;
            ">
                <div style="
                    width: {confidence}%;
                    height: 100%;
                    border-radius: 999px;
                    background: linear-gradient(
                        90deg,
                        {accent},
                        #C99374
                    );
                "></div>
            </div>

            <!-- Main insight grid -->
            <div style="
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 13px;
            ">

                <div style="
                    padding: 16px;
                    border-radius: 15px;
                    border: 1px solid #DDD1C2;
                    background: rgba(255, 253, 248, 0.82);
                ">
                    <div style="
                        margin-bottom: 7px;
                        color: #A06F58;
                        font-size: 10px;
                        font-weight: 850;
                        letter-spacing: 0.11em;
                        text-transform: uppercase;
                    ">
                        Likely root cause
                    </div>

                    <div style="
                        color: #4A3930;
                        font-size: 13px;
                        line-height: 1.62;
                    ">
                        {root_cause}
                    </div>
                </div>

                <div style="
                    padding: 16px;
                    border-radius: 15px;
                    border: 1px solid #DDD1C2;
                    background: rgba(255, 253, 248, 0.82);
                ">
                    <div style="
                        margin-bottom: 7px;
                        color: #A06F58;
                        font-size: 10px;
                        font-weight: 850;
                        letter-spacing: 0.11em;
                        text-transform: uppercase;
                    ">
                        Evidence Sam noticed
                    </div>

                    <div style="
                        color: #4A3930;
                        font-size: 13px;
                        line-height: 1.62;
                    ">
                        {evidence}
                    </div>
                </div>

                <div style="
                    padding: 16px;
                    border-radius: 15px;
                    border: 1px solid #D5D8C8;
                    background: #F2F3E9;
                ">
                    <div style="
                        margin-bottom: 7px;
                        color: #788069;
                        font-size: 10px;
                        font-weight: 850;
                        letter-spacing: 0.11em;
                        text-transform: uppercase;
                    ">
                        Micro-skill to strengthen
                    </div>

                    <div style="
                        color: #3F4538;
                        font-size: 13px;
                        line-height: 1.55;
                        font-weight: 750;
                    ">
                        {micro_skill}
                    </div>
                </div>

                <div style="
                    padding: 16px;
                    border-radius: 15px;
                    border: 1px solid #DDD1C2;
                    background: #FFF9EF;
                ">
                    <div style="
                        margin-bottom: 7px;
                        color: #A06F58;
                        font-size: 10px;
                        font-weight: 850;
                        letter-spacing: 0.11em;
                        text-transform: uppercase;
                    ">
                        Use this strategy
                    </div>

                    <div style="
                        color: #4A3930;
                        font-size: 13px;
                        line-height: 1.62;
                    ">
                        {strategy}
                    </div>
                </div>
            </div>

            <!-- Pattern intelligence -->
            <div style="
                margin-top: 13px;
                padding: 15px 16px;
                border-radius: 15px;
                border: 1px solid {accent}3D;
                background: {accent}10;
            ">
                <div style="
                    margin-bottom: 6px;
                    color: {accent};
                    font-size: 10px;
                    font-weight: 850;
                    letter-spacing: 0.11em;
                    text-transform: uppercase;
                ">
                    Pattern intelligence
                </div>

                <div style="
                    color: #4A3930;
                    font-size: 13px;
                    line-height: 1.6;
                ">
                    {student_pattern}
                </div>
            </div>

            <!-- Next step -->
            <div style="
                display: flex;
                align-items: flex-start;
                gap: 9px;
                margin-top: 15px;
                padding: 13px 15px;
                border-radius: 14px;
                border: 1px solid #E1D4B5;
                background: #FBF1D2;
            ">
                <div style="
                    color: #A46F39;
                    font-size: 12px;
                    line-height: 1.55;
                    font-weight: 850;
                    white-space: nowrap;
                ">
                    Next:
                </div>

                <div style="
                    color: #58452F;
                    font-size: 12px;
                    line-height: 1.55;
                ">
                    {next_step}
                </div>
            </div>

            <!-- Footer -->
            <div style="
                margin-top: 13px;
                color: #A39586;
                font-size: 9px;
                letter-spacing: 0.09em;
                line-height: 1.5;
                text-transform: uppercase;
            ">
                {esc(source_note)} · Diagnosis describes a likely pattern,
                not certainty
            </div>
        </div>
        """
    )
# ---- Feature 3: weakness-aware question targeting -----------------------

def ai_recommend_focus_skills(history):
    """Ask the model which skills to prioritize next. Returns a list of skill
    names drawn from the question bank, or [] on any failure."""
    stats = skill_stats(history)
    if not stats:
        return []

    performance = "\n".join(
        f"- {skill}: {record['acc']}% correct over {record['n']} question(s) "
        f"[{record['section']}]"
        for skill, record in sorted(stats.items(), key=lambda kv: kv[1]["acc"])
    )
    available = sorted({q["skill"] for q in QUESTIONS})

    system_prompt = (
        "You are an SAT prep strategist. You respond only with valid JSON."
    )
    user_prompt = (
        "A student's practice performance, weakest first:\n"
        f"{performance}\n\n"
        "Skills you may target (use these names exactly):\n"
        f"{', '.join(available)}\n\n"
        "Pick the three to five skills this student should drill next to gain the "
        "most points. Prioritize low accuracy, but also flag skills attempted very "
        "few times, since an untested skill is a hidden risk. Respond with JSON of "
        'the form {"focus_skills": ["exact skill name", ...]}.'
    )
    ok, text = ollama_chat(system_prompt, user_prompt, temperature=0.3,
                           force_json=True)
    if not ok:
        return []
    data = parse_json_response(text)
    if not isinstance(data, dict):
        return []
    valid = set(available)
    return [s for s in data.get("focus_skills", []) if s in valid]


# ---- Feature 4: end-of-session review -----------------------------------

def ai_session_review(entries):
    """Summarize a finished session and surface concrete next steps."""
    if not entries:
        return False, "No answers to review yet."

    correct = sum(1 for e in entries if e["correct"])
    total = len(entries)

    by_skill = {}
    for entry in entries:
        record = by_skill.setdefault(entry["skill"], {"n": 0, "c": 0})
        record["n"] += 1
        record["c"] += 1 if entry["correct"] else 0

    breakdown = "\n".join(
        f"- {skill}: {record['c']}/{record['n']} correct"
        for skill, record in by_skill.items()
    )
    missed = sorted({e["skill"] for e in entries if not e["correct"]})

    summary = (
        f"Session score: {correct}/{total} correct.\n"
        f"Accuracy by skill:\n{breakdown}\n"
        f"Skills with at least one miss: {', '.join(missed) if missed else 'none'}."
    )
    user_prompt = (
        "A student just finished an adaptive SAT practice session. Results:\n\n"
        f"{summary}\n\n"
        "Write a short review of about four to six sentences. Name the one or two "
        "skills they most need to work on, acknowledge what they handled well, and "
        "end with one concrete next step. Speak directly to the student and avoid "
        "Markdown headers."
    )
    return ollama_chat(build_coach_system_prompt(), user_prompt, temperature=0.5)


# ---- Feature 2: AI-generated study plan ---------------------------------

def ai_generate_study_plan():
    """Generate a personalized 7-day plan as structured data.
    Returns (True, plan_dict) or (False, error_message)."""
    stats = skill_stats(st.session_state.history)
    if stats:
        performance = "\n".join(
            f"- {skill}: {record['acc']}% over {record['n']} question(s) "
            f"[{record['section']}]"
            for skill, record in sorted(stats.items(), key=lambda kv: kv[1]["acc"])
        )
    else:
        performance = "No practice history yet — assume a balanced starting point."

    context = (
        f"Target score: {st.session_state.target_score}\n"
        f"Current predicted score: "
        f"{st.session_state.predicted_score or 'not yet estimated'}\n"
        f"Days until the SAT: {days_until_sat()}\n"
        f"Weekday time budget: {st.session_state.get('weekday_minutes', 45)} minutes\n"
        f"Weekend time budget: {st.session_state.get('weekend_minutes', 120)} minutes\n"
        f"Preferred lighter day: {st.session_state.get('rest_day', 'Sunday')}\n"
        f"Performance by skill (weakest first):\n{performance}"
    )
    system_prompt = (
        "You are an expert SAT tutor who designs realistic weekly study plans. "
        "You respond only with valid JSON."
    )
    user_prompt = (
        f"{context}\n\n"
        "Design a seven-day plan, Monday through Sunday, that attacks this "
        "student's weakest skills first while keeping math and reading balanced. "
        "Respect the weekday and weekend time budgets, and make the preferred "
        "lighter day genuinely lighter. Respond ONLY with JSON of this exact "
        "shape:\n"
        '{"strategy": "two or three sentence overview", '
        '"days": [{"day": "Monday", "minutes": 45, "focus": "skill or theme", '
        '"task": "short task name", "detail": "one specific sentence"}], '
        '"weekly_focus": "one sentence naming the week\'s top priority"}. '
        "Include exactly seven day objects, in order from Monday to Sunday."
    )
    ok, text = ollama_chat(system_prompt, user_prompt, temperature=0.4,
                           force_json=True)
    if not ok:
        return False, text
    data = parse_json_response(text)
    if not isinstance(data, dict) or not isinstance(data.get("days"), list):
        return False, "The model returned an unexpected format. Please try again."
    return True, data


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


# ============================================================
# METRICS DERIVED FROM ANSWER HISTORY
#
# Every dashboard number below is computed from the running
# history of answered questions, so the home page, insights,
# and sidebar all reflect real performance.
# ============================================================

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


# ============================================================
# SESSION STATE
# ============================================================

PAGES = [
    "Home",
    "Practice",
    "Insights",
    "Study Plan",
    "Focus Timer",
    "Settings",
]

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

    # AI tutor (local Ollama model) — consumed by the AI integration.
    "ai_enabled": True,
    "ai_host": "http://localhost:11434",
    "ai_model": "qwen3:8b",
    "ai_temperature": 0.7,
    "explanation_style": "Concise and strategic",
    "coach_personality": "Warm and focused",
    "ai_hints": True,

    # The most recent AI-generated study plan (persisted to settings).
    "ai_study_plan": None,

    # Skills the AI chose to target for the current session (runtime only).
    "ai_focus_skills": [],
    "error_fingerprint_cache": {},

    # Misc.
    "pomodoro_running": False,
}

saved_settings = load_settings()
for key, value in DEFAULT_STATE.items():
    if key in saved_settings:
        value = saved_settings[key]
    if key not in st.session_state:
        st.session_state[key] = value

# Pre-fill the Practice setup widgets from the saved session defaults. These
# apply on each fresh launch; per-session changes made in Practice still stick.
for widget_key, default_value in {
    "practice_subject": st.session_state.default_practice_subject,
    "practice_focus": "Highest-impact weakness",
    "practice_difficulty": st.session_state.default_start_difficulty,
    "practice_questions": st.session_state.default_practice_count,
    "practice_explanations": st.session_state.auto_explain,
}.items():
    if widget_key not in st.session_state:
        st.session_state[widget_key] = default_value

# Navigation requested by a button on the previous run. This has to
# be applied *before* the sidebar radio is created, because Streamlit
# refuses to let a widget's key be modified after instantiation.
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

    # Let the model prioritize which weak skills to target this session. When the
    # AI is off or unreachable, pick_next falls back to the accuracy heuristic.
    st.session_state.ai_focus_skills = []
    if (st.session_state.get("ai_enabled")
            and config["focus"] == "Highest-impact weakness"
            and st.session_state.history):
        with st.spinner("Sam is analyzing your weak spots…"):
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


# Refresh derived metrics for this run now that history is available.
recompute_metrics()


# ============================================================
# HELPERS
# ============================================================

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


def metric_card(label, value, detail, icon):
    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-top">
                <span class="metric-icon">{icon}</span>
                <span class="metric-label">{esc(label)}</span>
            </div>
            <div class="metric-value">{esc(value)}</div>
            <div class="metric-detail">{esc(detail)}</div>
        </div>
        """
    )


def section_header(eyebrow, title, description=""):
    render_html(
        f"""
        <div class="section-heading">
            <div class="eyebrow">{esc(eyebrow)}</div>
            <h2>{esc(title)}</h2>
            <p>{esc(description)}</p>
        </div>
        """
    )


def topic_row(topic, accuracy_value, status):
    status_class = status.lower().replace(" ", "-")
    width = max(0, min(accuracy_value, 100))
    render_html(
        f"""
        <div class="topic-row">
            <div class="topic-row-top">
                <div>
                    <div class="topic-name">{esc(topic)}</div>
                    <div class="topic-status {status_class}">{esc(status)}</div>
                </div>
                <div class="topic-score">{accuracy_value}%</div>
            </div>
            <div class="topic-progress-track">
                <div class="topic-progress-fill" style="width: {width}%;"></div>
            </div>
        </div>
        """
    )


def empty_state(message):
    render_html(
        f'<p style="color: var(--muted); font-size: 0.85rem; margin: 0.5rem 0;">{esc(message)}</p>'
    )


# ============================================================
# GLOBAL STYLING
# ============================================================

STYLES = """
<style>

/* ----- IMPORT FONT ----- */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap');

/* ----- ROOT DESIGN TOKENS ----- */
:root {
    --cream: #F8F3EA;
    --paper: #FFFDF8;
    --paper-muted: #F3EDE3;
    --ink: #28241F;
    --muted: #746D63;
    --terracotta: #C9694A;
    --terracotta-dark: #A95036;
    --terracotta-soft: #F2D8CB;
    --sage: #6F856F;
    --sage-soft: #DEE7DC;
    --mustard: #D9A441;
    --mustard-soft: #F5E7BC;
    --blue-soft: #DDE8EB;
    --border: #E6DDD1;
    --shadow: 0 14px 35px rgba(70, 53, 38, 0.08);
    --shadow-small: 0 5px 16px rgba(70, 53, 38, 0.06);
}

/* ----- APP FOUNDATION ----- */
html, body, [class*="css"] {
    font-family: "DM Sans", sans-serif;
    color: var(--ink);
}
.stApp {
    background:
        radial-gradient(circle at 84% 4%, rgba(217, 164, 65, 0.13), transparent 24rem),
        radial-gradient(circle at 10% 95%, rgba(111, 133, 111, 0.12), transparent 28rem),
        var(--cream);
}
.block-container {
    max-width: 1380px;
    padding-top: 2rem;
    padding-bottom: 4rem;
    padding-left: 2.7rem;
    padding-right: 2.7rem;
}
h1, h2, h3 { color: var(--ink); }
p { color: var(--muted); }
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
#MainMenu,
footer { visibility: hidden; }

/* Any HTML that still slips through markdown should not become a dark block. */
.stApp pre, .stApp code {
    background: var(--paper-muted);
    color: var(--ink);
}

/* ----- SIDEBAR ----- */
section[data-testid="stSidebar"] {
    background: #F1E9DE;
    border-right: 1px solid #E0D5C7;
}
section[data-testid="stSidebar"] > div { padding-top: 1.25rem; }
.sidebar-brand { padding: 0.4rem 0.35rem 1.2rem 0.35rem; }
.sidebar-brand-row { display: flex; align-items: center; gap: 0.75rem; }
.brand-mark {
    width: 42px;
    height: 42px;
    border-radius: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--terracotta);
    color: white;
    font-size: 1.25rem;
    box-shadow: 0 7px 16px rgba(169, 80, 54, 0.21);
}
.brand-name {
    font-family: "Newsreader", serif;
    font-size: 1.65rem;
    font-weight: 600;
    line-height: 1;
    color: var(--ink);
}
.brand-caption { color: var(--muted); font-size: 0.74rem; margin-top: 0.16rem; }
.sidebar-label {
    color: #877E72;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.65rem;
    font-weight: 700;
    margin: 0.8rem 0 0.5rem 0.25rem;
}
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 0.25rem; }
section[data-testid="stSidebar"] label[data-baseweb="radio"] {
    background: transparent;
    padding: 0.72rem 0.8rem;
    border-radius: 11px;
    transition: all 0.18s ease;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
    background: rgba(255, 255, 255, 0.48);
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
    background: var(--paper);
    box-shadow: var(--shadow-small);
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p {
    color: var(--terracotta-dark);
    font-weight: 700;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {
    display: none;
}
.sidebar-card {
    background: rgba(255, 253, 248, 0.7);
    border: 1px solid rgba(222, 210, 195, 0.9);
    padding: 1rem;
    border-radius: 15px;
    margin-top: 1rem;
}
.sidebar-card-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-weight: 700;
    color: #8B8175;
}
.sidebar-card-value {
    font-size: 1rem;
    font-weight: 700;
    color: var(--ink);
    margin-top: 0.35rem;
}
.sidebar-card-detail { font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }
.mini-progress {
    height: 7px;
    width: 100%;
    border-radius: 999px;
    background: #E4DACE;
    overflow: hidden;
    margin-top: 0.8rem;
}
.mini-progress-fill { height: 100%; border-radius: inherit; background: var(--terracotta); }

/* ----- HERO ----- */
.hero {
    position: relative;
    overflow: hidden;
    min-height: 252px;
    padding: 2.5rem 2.65rem;
    margin-bottom: 1.65rem;
    border-radius: 26px;
    background: linear-gradient(125deg, rgba(255, 253, 248, 0.98), rgba(244, 226, 210, 0.95));
    border: 1px solid rgba(215, 193, 173, 0.8);
    box-shadow: var(--shadow);
}
.hero::after {
    content: "";
    position: absolute;
    right: -70px;
    top: -100px;
    width: 380px;
    height: 380px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(201, 105, 74, 0.25) 0%, rgba(217, 164, 65, 0.12) 44%, transparent 70%);
}
.hero::before {
    content: "✦";
    position: absolute;
    right: 128px;
    top: 46px;
    font-size: 5.8rem;
    color: rgba(169, 80, 54, 0.16);
    transform: rotate(12deg);
    z-index: 1;
}
.hero-content { position: relative; z-index: 2; max-width: 760px; }
.hero-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.46rem 0.78rem;
    border-radius: 999px;
    background: rgba(255, 253, 248, 0.72);
    border: 1px solid rgba(201, 105, 74, 0.18);
    color: var(--terracotta-dark);
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.035em;
    margin-bottom: 1rem;
}
.hero h1 {
    font-family: "Newsreader", serif;
    font-size: clamp(2.7rem, 5vw, 4.35rem);
    line-height: 0.98;
    letter-spacing: -0.045em;
    margin: 0;
    max-width: 760px;
}
.hero h1 span { color: var(--terracotta); }
.hero p {
    max-width: 610px;
    font-size: 1rem;
    line-height: 1.65;
    margin: 1rem 0 0 0;
    color: #6F665B;
}
.hero-chips { display: flex; flex-wrap: wrap; gap: 0.65rem; margin-top: 1.35rem; }
.hero-chip {
    background: rgba(255, 253, 248, 0.7);
    border: 1px solid rgba(193, 169, 149, 0.5);
    border-radius: 999px;
    padding: 0.48rem 0.75rem;
    color: #655D53;
    font-size: 0.77rem;
    font-weight: 600;
}

/* ----- METRIC CARDS ----- */
.metric-card {
    min-height: 158px;
    background: rgba(255, 253, 248, 0.91);
    border: 1px solid var(--border);
    border-radius: 19px;
    padding: 1.2rem;
    box-shadow: var(--shadow-small);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.metric-card:hover { transform: translateY(-3px); box-shadow: var(--shadow); }
.metric-top { display: flex; align-items: center; gap: 0.55rem; }
.metric-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 31px;
    height: 31px;
    border-radius: 10px;
    background: var(--paper-muted);
    color: var(--terracotta-dark);
    font-size: 0.92rem;
}
.metric-label { color: var(--muted); font-size: 0.75rem; font-weight: 600; }
.metric-value {
    font-family: "Newsreader", serif;
    font-size: 2.25rem;
    font-weight: 600;
    color: var(--ink);
    line-height: 1;
    margin-top: 1rem;
}
.metric-detail { color: #8A8176; font-size: 0.72rem; margin-top: 0.55rem; }

/* ----- GENERAL CARDS AND HEADINGS ----- */
.section-heading { margin: 2.25rem 0 1rem 0; }
.section-heading .eyebrow {
    color: var(--terracotta-dark);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.66rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
}
.section-heading h2 {
    font-family: "Newsreader", serif;
    font-size: 2rem;
    letter-spacing: -0.025em;
    margin: 0;
}
.section-heading p { margin: 0.38rem 0 0 0; font-size: 0.88rem; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(255, 253, 248, 0.92);
    border: 1px solid var(--border);
    border-radius: 21px;
    box-shadow: var(--shadow-small);
}
div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 1.3rem; }
.card-title {
    font-family: "Newsreader", serif;
    color: var(--ink);
    font-size: 1.45rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}
.card-subtitle { color: var(--muted); font-size: 0.8rem; margin-bottom: 1rem; }

/* ----- DAILY PLAN ----- */
.plan-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.95rem 0;
    border-bottom: 1px solid #EEE7DE;
}
.plan-item:last-child { border-bottom: none; }
.plan-left { display: flex; align-items: center; gap: 0.85rem; }
.plan-number {
    width: 36px;
    height: 36px;
    min-width: 36px;
    border-radius: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--paper-muted);
    color: var(--terracotta-dark);
    font-weight: 700;
    font-size: 0.75rem;
}
.plan-name { color: var(--ink); font-size: 0.88rem; font-weight: 700; }
.plan-description { color: var(--muted); font-size: 0.72rem; margin-top: 0.15rem; }
.plan-time { color: #766E63; font-size: 0.72rem; font-weight: 600; white-space: nowrap; }

/* ----- AI INSIGHT ----- */
.ai-insight {
    position: relative;
    overflow: hidden;
    padding: 1.25rem;
    border-radius: 17px;
    background: linear-gradient(135deg, var(--sage-soft), #EDF1E8);
    border: 1px solid #CFDBCB;
    margin-bottom: 1rem;
}
.ai-insight-label {
    color: #536853;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.65rem;
    font-weight: 800;
}
.ai-insight h3 { font-family: "Newsreader", serif; font-size: 1.45rem; margin: 0.4rem 0; }
.ai-insight p { color: #5C685B; font-size: 0.8rem; line-height: 1.55; margin: 0; }
.coach-quote {
    padding: 1.05rem 1.1rem;
    border-left: 3px solid var(--mustard);
    border-radius: 0 14px 14px 0;
    background: var(--mustard-soft);
    color: #705D34;
    font-family: "Newsreader", serif;
    font-size: 1.05rem;
    line-height: 1.45;
}

/* ----- PROGRESS RING ----- */
.progress-ring-card { text-align: center; padding: 0.5rem 0 0.2rem 0; }
.progress-ring {
    --progress: 62%;
    width: 142px;
    height: 142px;
    margin: 0.4rem auto 1rem auto;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: conic-gradient(var(--terracotta) var(--progress), #EAE1D6 0);
    position: relative;
}
.progress-ring::after {
    content: "";
    position: absolute;
    width: 111px;
    height: 111px;
    border-radius: 50%;
    background: var(--paper);
}
.progress-ring-content { position: relative; z-index: 2; }
.progress-ring-value {
    font-family: "Newsreader", serif;
    font-weight: 600;
    font-size: 1.75rem;
    color: var(--ink);
}
.progress-ring-label { color: var(--muted); font-size: 0.68rem; }

/* ----- TOPIC ANALYTICS ----- */
.topic-row { padding: 1rem 0; border-bottom: 1px solid #EEE6DC; }
.topic-row:last-child { border-bottom: none; }
.topic-row-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.65rem;
}
.topic-name { color: var(--ink); font-weight: 700; font-size: 0.85rem; }
.topic-score {
    color: var(--ink);
    font-family: "Newsreader", serif;
    font-size: 1.15rem;
    font-weight: 600;
}
.topic-status {
    display: inline-block;
    margin-top: 0.22rem;
    font-size: 0.65rem;
    font-weight: 700;
}
.needs-work { color: var(--terracotta-dark); }
.developing { color: #9A712A; }
.strong { color: #567056; }
.topic-progress-track {
    width: 100%;
    height: 7px;
    background: #ECE4DA;
    overflow: hidden;
    border-radius: 999px;
}
.topic-progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--terracotta), var(--mustard));
}

/* ----- ACTIVITY ----- */
.activity-item {
    display: flex;
    gap: 0.8rem;
    padding: 0.85rem 0;
    border-bottom: 1px solid #EEE7DE;
}
.activity-item:last-child { border-bottom: none; }
.activity-dot {
    width: 10px;
    height: 10px;
    min-width: 10px;
    border-radius: 50%;
    background: var(--sage);
    margin-top: 0.32rem;
    box-shadow: 0 0 0 4px var(--sage-soft);
}
.activity-dot.miss { background: var(--terracotta); box-shadow: 0 0 0 4px var(--terracotta-soft); }
.activity-title { color: var(--ink); font-size: 0.8rem; font-weight: 700; }
.activity-detail { color: var(--muted); font-size: 0.69rem; margin-top: 0.15rem; }

/* ----- PRACTICE QUESTION ----- */
.practice-header {
    padding: 1.2rem 1.3rem;
    border-radius: 18px;
    background: linear-gradient(125deg, var(--terracotta-soft), #F6E8D7);
    border: 1px solid #E9CDBD;
    margin-bottom: 1.2rem;
}
.practice-header-label {
    color: var(--terracotta-dark);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.66rem;
    font-weight: 700;
}
.practice-header h2 { font-family: "Newsreader", serif; font-size: 1.8rem; margin: 0.3rem 0 0.2rem 0; }
.question-number {
    color: var(--terracotta-dark);
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-size: 0.68rem;
    font-weight: 700;
}
.question-text {
    font-family: "Newsreader", serif;
    color: var(--ink);
    font-size: 1.45rem;
    line-height: 1.4;
    margin: 0.7rem 0 1.1rem 0;
}
.formula-box {
    padding: 1rem;
    text-align: center;
    background: var(--paper-muted);
    border: 1px solid var(--border);
    border-radius: 13px;
    color: var(--ink);
    font-family: Georgia, serif;
    font-size: 1.2rem;
    margin-bottom: 1rem;
}
.stimulus-box {
    padding: 1rem 1.1rem;
    background: var(--paper-muted);
    border: 1px solid var(--border);
    border-radius: 13px;
    color: var(--ink);
    font-size: 0.97rem;
    line-height: 1.55;
    margin: 0.2rem 0 1rem 0;
}
.review-choice {
    padding: 0.6rem 0.85rem;
    border: 1px solid var(--border);
    border-radius: 11px;
    margin-bottom: 0.45rem;
    font-size: 0.9rem;
    color: var(--ink);
    background: var(--paper);
}
.review-choice.correct {
    border-color: #8CAE8C;
    background: #EAF1E7;
    color: #3F553F;
    font-weight: 700;
}
.review-choice.wrong {
    border-color: #D9A08C;
    background: #F7E7DF;
    color: #9A4B33;
}
.review-choice .tag { float: right; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em; }

/* ----- STUDY PLAN DAYS ----- */
.day-card {
    padding: 1.1rem;
    border-radius: 16px;
    background: var(--paper);
    border: 1px solid var(--border);
    margin-bottom: 0.75rem;
}
.day-name {
    color: var(--terracotta-dark);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-weight: 800;
}
.day-task { color: var(--ink); font-weight: 700; font-size: 0.9rem; margin-top: 0.35rem; }
.day-detail { color: var(--muted); font-size: 0.72rem; margin-top: 0.25rem; }

/* ----- BUTTONS ----- */
.stButton > button {
    min-height: 44px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--paper);
    color: var(--ink);
    font-weight: 700;
    font-size: 0.82rem;
    box-shadow: none;
    transition: all 0.18s ease;
}
.stButton > button:hover {
    color: var(--terracotta-dark);
    border-color: #D9B09F;
    background: #FFF9F3;
    transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    color: white;
    background: var(--terracotta);
    border-color: var(--terracotta);
    box-shadow: 0 7px 17px rgba(169, 80, 54, 0.2);
}
.stButton > button[kind="primary"]:hover {
    color: white;
    background: var(--terracotta-dark);
    border-color: var(--terracotta-dark);
}

/* ----- INPUTS ----- */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stDateInput"] input {
    background: var(--paper);
    border-color: var(--border);
    border-radius: 11px;
}
div[data-baseweb="slider"] div[role="slider"] { background: var(--terracotta); }
div[data-baseweb="slider"] > div > div { background: var(--terracotta); }
div[data-testid="stProgress"] > div > div > div { background: var(--terracotta); }

/* ----- RADIO OPTIONS IN THE MAIN AREA ----- */
div[data-testid="stMain"] div[role="radiogroup"] { gap: 0.55rem; }
div[data-testid="stMain"] label[data-baseweb="radio"] {
    background: var(--paper);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.78rem 0.9rem;
}
div[data-testid="stMain"] label[data-baseweb="radio"]:has(input:checked) {
    border-color: var(--terracotta);
    background: #FFF7F2;
}

/* ----- STREAMLIT ALERTS ----- */
div[data-testid="stAlert"] { border-radius: 14px; border: 1px solid var(--border); }

/* ----- RESPONSIVE ----- */
@media (max-width: 900px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .hero { padding: 1.8rem; }
    .hero::before { display: none; }
}

</style>
"""

render_html(STYLES)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    render_html(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-row">
                <div class="brand-mark">S</div>
                <div>
                    <div class="brand-name">SATSam</div>
                    <div class="brand-caption">Thoughtful SAT preparation</div>
                </div>
            </div>
        </div>
        """
    )

    render_html('<div class="sidebar-label">Workspace</div>')

    page = st.radio(
        "Navigation",
        PAGES,
        key="page",
        label_visibility="collapsed",
    )

    render_html(
        f"""
        <div class="sidebar-card">
            <div class="sidebar-card-label">Next SAT</div>
            <div class="sidebar-card-value">
                {format_sat_date()}
            </div>
            <div class="sidebar-card-detail">{days_until_sat()} days remaining</div>
            <div class="mini-progress">
                <div class="mini-progress-fill" style="width: {prep_window_percent()}%;"></div>
            </div>
        </div>
        <div class="sidebar-card">
            <div class="sidebar-card-label">Current streak</div>
            <div class="sidebar-card-value">{st.session_state.streak} focused days</div>
            <div class="sidebar-card-detail">Your best streak is {st.session_state.best_streak} days</div>
        </div>
        """
    )

    st.write("")

    if st.button(
        "Start quick practice",
        type="primary",
        use_container_width=True,
    ):
        start_session(quick_session_config())
        go_to("Practice")


# ============================================================
# HOME PAGE
# ============================================================

if page == "Home":
    history = st.session_state.history
    has_data = len(history) > 0

    goal = max(st.session_state.study_goal, 1)
    progress_fraction = min(st.session_state.today_minutes / goal, 1.0)
    progress_percent = round(progress_fraction * 100)

    weak = weakest_skills(history)
    focus_label = weak[0] if weak else "Balanced practice"

    render_html(
        f"""
        <div class="hero">
            <div class="hero-content">
                <div class="hero-kicker">✦ Your personalized plan is ready</div>
                <h1>{greeting()},<br>let's study with <span>purpose.</span></h1>
                <p>
                    SATSam turns every answer into a clearer picture of how you
                    think, then builds the next lesson around exactly what you need.
                </p>
                <div class="hero-chips">
                    <div class="hero-chip">{days_until_sat()} days until test day</div>
                    <div class="hero-chip">Target: {st.session_state.target_score}</div>
                    <div class="hero-chip">Focus: {esc(focus_label)}</div>
                </div>
            </div>
        </div>
        """
    )

    # ----- Predicted-score delta detail -----
    score_log = st.session_state.score_history
    if len(score_log) >= 2:
        delta = score_log[-1] - score_log[0]
        pred_detail = f"{'+' if delta >= 0 else ''}{delta} points so far"
    elif has_data:
        pred_detail = "First estimate from your answers"
    else:
        pred_detail = "Answer questions to estimate"

    num_skills = len(skill_stats(history))

    metric_columns = st.columns(4)

    with metric_columns[0]:
        metric_card(
            "Predicted score",
            st.session_state.predicted_score if has_data else "—",
            pred_detail,
            "↗",
        )

    with metric_columns[1]:
        metric_card(
            "Overall accuracy",
            f"{accuracy()}%",
            f"Across {st.session_state.questions_solved} questions",
            "✓",
        )

    with metric_columns[2]:
        metric_card(
            "Study time",
            f"{st.session_state.study_minutes // 60}h "
            f"{st.session_state.study_minutes % 60}m",
            f"{st.session_state.sessions_completed} sessions completed",
            "◷",
        )

    with metric_columns[3]:
        metric_card(
            "Questions mastered",
            st.session_state.questions_mastered,
            f"Across {num_skills} skill{'s' if num_skills != 1 else ''}",
            "◇",
        )

    section_header(
        "Today's path",
        "A focused session, built for you",
        "SATSam prioritizes the skills most likely to improve your score.",
    )

    main_left, main_right = st.columns([1.65, 1], gap="large")

    with main_left:
        with st.container(border=True):
            render_html(
                f"""
                <div class="card-title">Your {st.session_state.study_goal}-minute session</div>
                <div class="card-subtitle">
                    Balanced practice based on your latest performance
                </div>
                <div class="plan-item">
                    <div class="plan-left">
                        <div class="plan-number">01</div>
                        <div>
                            <div class="plan-name">Warm-up questions</div>
                            <div class="plan-description">Two confidence-builders to start</div>
                        </div>
                    </div>
                    <div class="plan-time">8 min</div>
                </div>
                <div class="plan-item">
                    <div class="plan-left">
                        <div class="plan-number">02</div>
                        <div>
                            <div class="plan-name">Adaptive practice set</div>
                            <div class="plan-description">Difficulty adjusts after every response</div>
                        </div>
                    </div>
                    <div class="plan-time">20 min</div>
                </div>
                <div class="plan-item">
                    <div class="plan-left">
                        <div class="plan-number">03</div>
                        <div>
                            <div class="plan-name">Targeted weak-skill drill</div>
                            <div class="plan-description">Focused on {esc(focus_label)}</div>
                        </div>
                    </div>
                    <div class="plan-time">12 min</div>
                </div>
                <div class="plan-item">
                    <div class="plan-left">
                        <div class="plan-number">04</div>
                        <div>
                            <div class="plan-name">Mistake reflection</div>
                            <div class="plan-description">Turn one error into a reusable strategy</div>
                        </div>
                    </div>
                    <div class="plan-time">5 min</div>
                </div>
                """
            )

            st.write("")

            if st.button(
                "Begin today's session →",
                type="primary",
                use_container_width=True,
            ):
                start_session(quick_session_config())
                go_to("Practice")

    with main_right:
        with st.container(border=True):
            render_html(
                f"""
                <div class="card-title">Daily progress</div>
                <div class="card-subtitle">Keep the session manageable and consistent</div>
                <div class="progress-ring-card">
                    <div class="progress-ring" style="--progress: {progress_percent}%;">
                        <div class="progress-ring-content">
                            <div class="progress-ring-value">{st.session_state.today_minutes}</div>
                            <div class="progress-ring-label">
                                of {st.session_state.study_goal} minutes
                            </div>
                        </div>
                    </div>
                </div>
                """
            )

            st.progress(progress_fraction)

            remaining = max(
                st.session_state.study_goal - st.session_state.today_minutes,
                0,
            )
            st.caption(f"{remaining} focused minutes remaining today")

        st.write("")

        if has_data:
            insight_body = (
                f"You have answered {st.session_state.questions_solved} "
                f"question{'s' if st.session_state.questions_solved != 1 else ''} "
                f"at {accuracy()}% accuracy. "
                + (
                    f"Your softest area right now is {focus_label} — today's drill leans there."
                    if weak else
                    "Keep going to reveal where your next points are hiding."
                )
            )
            insight_head = "Here's where you stand."
        else:
            insight_body = (
                "Answer a few practice questions and SATSam will start building "
                "a picture of how you think — accuracy, pacing, and which skills "
                "to prioritize."
            )
            insight_head = "Let's gather some signal."

        render_html(
            f"""
            <div class="ai-insight">
                <div class="ai-insight-label">Sam's observation</div>
                <h3>{esc(insight_head)}</h3>
                <p>{esc(insight_body)}</p>
            </div>
            """
        )

        render_html(
            """
            <div class="coach-quote">
                &ldquo;Accuracy first. Speed follows familiarity.&rdquo;
            </div>
            """
        )

    section_header(
        "Performance snapshot",
        "Know what to strengthen next",
        "Each recommendation connects directly to your recent answers.",
    )

    topic_col, activity_col = st.columns([1.2, 1], gap="large")

    stats = skill_stats(history)

    with topic_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Topic confidence</div>
                <div class="card-subtitle">
                    Estimated from your accuracy on each skill
                </div>
                """
            )

            if stats:
                top_skills = sorted(
                    stats.items(), key=lambda kv: kv[1]["n"], reverse=True
                )[:5]
                for skill, record in top_skills:
                    topic_row(skill, record["acc"], status_for_accuracy(record["acc"]))
            else:
                empty_state(
                    "No skill data yet. Complete a practice session to see your "
                    "topic confidence build here."
                )

    with activity_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Recent learning</div>
                <div class="card-subtitle">The work behind your score growth</div>
                """
            )

            if history:
                for entry in reversed(history[-4:]):
                    dot_class = "" if entry["correct"] else "miss"
                    verdict = "Correct" if entry["correct"] else "Missed"
                    render_html(
                        f"""
                        <div class="activity-item">
                            <div class="activity-dot {dot_class}"></div>
                            <div>
                                <div class="activity-title">{esc(entry['skill'])}</div>
                                <div class="activity-detail">
                                    {verdict} · {esc(entry['difficulty'].title())} · {relative_time(entry['ts'])}
                                </div>
                            </div>
                        </div>
                        """
                    )
            else:
                empty_state("Your answered questions will appear here as you practice.")


# ============================================================
# PRACTICE PAGE
# ============================================================

elif page == "Practice":
    render_html(
        """
        <div class="practice-header">
            <div class="practice-header-label">Adaptive practice</div>
            <h2>Build a session around today's needs.</h2>
            <p>
                Select a focus or let SATSam choose the highest-impact
                combination automatically.
            </p>
        </div>
        """
    )

    if not QUESTIONS:
        st.error(
            "No questions are loaded. Make sure **sat-questions.json** sits in "
            "the same folder as this app, then refresh."
        )
    else:
        phase = st.session_state.practice_phase

        # ---------------- SETUP ----------------
        if phase == "setup":
            setup_col, recommendation_col = st.columns([1.4, 1], gap="large")

            with setup_col:
                with st.container(border=True):
                    render_html(
                        """
                        <div class="card-title">Session setup</div>
                        <div class="card-subtitle">
                            Customize the challenge without overthinking it
                        </div>
                        """
                    )

                    st.selectbox(
                        "Subject",
                        [
                            "SATSam recommendation",
                            "Math",
                            "Reading and Writing",
                            "Balanced",
                        ],
                        key="practice_subject",
                    )

                    st.selectbox(
                        "Primary focus",
                        [
                            "Highest-impact weakness",
                            "Linear equations",
                            "Problem solving and data",
                            "Reading inference",
                            "Grammar conventions",
                        ],
                        key="practice_focus",
                    )

                    st.select_slider(
                        "Starting difficulty",
                        options=[
                            "Foundation",
                            "Standard",
                            "Challenging",
                            "Test-level",
                        ],
                        key="practice_difficulty",
                    )

                    st.slider(
                        "Questions",
                        min_value=5,
                        max_value=30,
                        step=1,
                        key="practice_questions",
                    )

                    st.toggle(
                        "Explain each answer immediately",
                        key="practice_explanations",
                    )

                    st.write("")

                    if st.button(
                        "Create adaptive session →",
                        type="primary",
                        use_container_width=True,
                    ):
                        config = {
                            "subject": st.session_state.practice_subject,
                            "focus": st.session_state.practice_focus,
                            "start_difficulty": START_DIFFICULTY.get(
                                st.session_state.practice_difficulty, "medium"
                            ),
                            "count": st.session_state.practice_questions,
                            "explain": st.session_state.practice_explanations,
                        }
                        start_session(config)
                        st.rerun()

            with recommendation_col:
                render_html(
                    """
                    <div class="ai-insight">
                        <div class="ai-insight-label">How this works</div>
                        <h3>Real questions, adaptive order</h3>
                        <p>
                            Every question is drawn from the practice bank. Answer
                            correctly and the next one steps up in difficulty; miss
                            it and SATSam eases back so you can rebuild the skill.
                        </p>
                    </div>
                    """
                )

                with st.container(border=True):
                    render_html(
                        """
                        <div class="card-title">How adaptation works</div>
                        <div class="card-subtitle">
                            More than simply making questions harder
                        </div>
                        <div class="plan-item">
                            <div class="plan-left">
                                <div class="plan-number">A</div>
                                <div>
                                    <div class="plan-name">Track each response</div>
                                    <div class="plan-description">Right and wrong answers both inform the next pick</div>
                                </div>
                            </div>
                        </div>
                        <div class="plan-item">
                            <div class="plan-left">
                                <div class="plan-number">B</div>
                                <div>
                                    <div class="plan-name">Adjust difficulty</div>
                                    <div class="plan-description">Difficulty shifts up or down after every answer</div>
                                </div>
                            </div>
                        </div>
                        <div class="plan-item">
                            <div class="plan-left">
                                <div class="plan-number">C</div>
                                <div>
                                    <div class="plan-name">Explain the pattern</div>
                                    <div class="plan-description">Every answer comes with a full worked explanation</div>
                                </div>
                            </div>
                        </div>
                        """
                    )

        # ---------------- EMPTY (no match) ----------------
        elif phase == "empty":
            st.info(
                "No questions matched those filters. Try a broader subject or a "
                "different focus."
            )
            if st.button("Back to setup", type="primary"):
                st.session_state.practice_phase = "setup"
                st.rerun()

        # ---------------- QUESTION ----------------
        elif phase == "question":
            question = st.session_state.current_q
            config = st.session_state.session_config
            count = config["count"]
            answered = st.session_state.session_answered
            submitted = st.session_state.answer_submitted

            question_col, context_col = st.columns([1.65, 0.85], gap="large")

            with question_col:
                with st.container(border=True):
                    # Before submitting, this is question (answered + 1). After
                    # submitting, answered has been incremented to include it.
                    display_number = answered + 1 if not submitted else answered
                    render_html(
                        f'<div class="question-number">Question {display_number} of {count} · '
                        f'{esc(question["domain"])} · {esc(question["difficulty"].title())}</div>'
                    )

                    if question.get("stimulus"):
                        render_html(
                            f'<div class="stimulus-box">{to_html_block(question["stimulus"])}</div>'
                        )

                    render_html(
                        f'<div class="question-text">{to_html_block(question["prompt"])}</div>'
                    )

                    is_mcq = question["format"] == "mcq"

                    if not submitted:
                        # ----- Input -----
                        if is_mcq:
                            choice_ids = [c["id"] for c in question["choices"]]
                            choice_text = {c["id"]: c["text"] for c in question["choices"]}
                            user_answer = st.radio(
                                "Select one answer",
                                choice_ids,
                                index=None,
                                format_func=lambda cid: f"{cid}.  {choice_text[cid]}",
                                key=f"ans_{question['id']}",
                            )
                        else:
                            st.caption("Student-produced response — type a numeric answer.")
                            user_answer = st.text_input(
                                "Your answer",
                                key=f"spr_{question['id']}",
                                placeholder="e.g. 5 or -4",
                            )

                        no_answer = user_answer is None or (
                            isinstance(user_answer, str) and user_answer.strip() == ""
                        )

                        button_col_1, button_col_2 = st.columns([1, 1])

                        with button_col_1:
                            if st.button("Leave session", use_container_width=True):
                                st.session_state.practice_phase = "setup"
                                st.session_state.answer_submitted = False
                                st.rerun()

                        with button_col_2:
                            if st.button(
                                "Submit answer →",
                                type="primary",
                                use_container_width=True,
                                disabled=no_answer,
                            ):
                                is_correct = check_answer(question, user_answer)
                                elapsed = min(
                                    time.time() - st.session_state.question_start, 600
                                )
                                st.session_state.history.append({
                                    "id": question["id"],
                                    "skill": question["skill"],
                                    "domain": question["domain"],
                                    "section": question["section"],
                                    "difficulty": question["difficulty"],
                                    "correct": is_correct,
                                    "student_answer": str(user_answer),
                                    "correct_answer": str(question.get("correct")),
                                    "seconds": elapsed,
                                    "est": question.get("estimated_seconds") or 0,
                                    "fingerprint": None,
                                    "ts": datetime.now(),
                                })
                                st.session_state.session_used_ids.add(question["id"])
                                st.session_state.session_answered += 1
                                st.session_state.session_correct += 1 if is_correct else 0
                                st.session_state.session_seconds += elapsed
                                st.session_state.current_difficulty = shift_difficulty(
                                    st.session_state.current_difficulty, is_correct
                                )
                                st.session_state.session_last_answer = user_answer
                                st.session_state.session_last_correct = is_correct
                                st.session_state.answer_submitted = True
                                st.rerun()

                    else:
                        # ----- Answer review -----
                        last_answer = st.session_state.session_last_answer
                        last_correct = st.session_state.session_last_correct

                        if is_mcq:
                            review_html = ""
                            for choice in question["choices"]:
                                css = ""
                                tag = ""
                                if choice["id"] == question["correct"]:
                                    css, tag = "correct", "Correct"
                                elif choice["id"] == last_answer:
                                    css, tag = "wrong", "Your answer"
                                review_html += (
                                    f'<div class="review-choice {css}">'
                                    f'{esc(choice["id"])}.  {esc(choice["text"])}'
                                    f'<span class="tag">{tag}</span></div>'
                                )
                            render_html(review_html)
                        else:
                            your_css = "correct" if last_correct else "wrong"
                            render_html(
                                f'<div class="review-choice {your_css}">Your answer: '
                                f'{esc(last_answer)}<span class="tag">You</span></div>'
                                f'<div class="review-choice correct">Correct answer: '
                                f'{esc(question["correct"])}<span class="tag">Correct</span></div>'
                            )

                        if last_correct:
                            st.success("Correct — nicely done.")
                        else:
                            st.error("Not quite. Sam is diagnosing the reasoning pattern behind this miss.")

                            latest_attempt = (
                                st.session_state.history[-1]
                                if st.session_state.history
                                else {}
                            )

                            elapsed_for_attempt = latest_attempt.get("seconds", 0)

                            if st.session_state.get("ai_enabled"):
                                with st.spinner("Sam is building your Error Fingerprint…"):
                                    fingerprint = get_error_fingerprint(
                                        question,
                                        last_answer,
                                        elapsed_for_attempt,
                                    )
                            else:
                                fingerprint = fallback_error_fingerprint(
                                    question,
                                    last_answer,
                                    elapsed_for_attempt,
                                )

                                if latest_attempt.get("id") == question.get("id"):
                                    latest_attempt["fingerprint"] = fingerprint

                            render_error_fingerprint(fingerprint)

                        if config.get("explain", True):
                            # Prefer a fresh, catered explanation from the local
                            # model; fall back to the bank's stored explanation if
                            # the AI is off or unreachable.
                            explanation_text = question["explanation"]
                            explanation_label = "Sam's explanation"
                            if st.session_state.get("ai_enabled"):
                                with st.spinner("Sam is working through this one…"):
                                    ok, ai_text = get_ai_explanation(
                                        question, last_answer, last_correct
                                    )
                                if ok and ai_text:
                                    explanation_text = ai_text
                                else:
                                    explanation_label = "Explanation"
                            else:
                                explanation_label = "Explanation"

                            render_html(
                                f"""
                                <div class="ai-insight">
                                    <div class="ai-insight-label">{esc(explanation_label)}</div>
                                    <h3>{esc(question["skill"])}</h3>
                                    <p>{to_html_block(explanation_text)}</p>
                                </div>
                                """
                            )

                            # If they picked a specific wrong MCQ choice, surface
                            # the rationale for that distractor.
                            if (not last_correct) and is_mcq:
                                note = question.get("distractors", {}).get(last_answer)
                                if note:
                                    st.caption(f"Why that option was tempting: {note}")

                        # ----- Advance -----
                        finishing = st.session_state.session_answered >= count
                        next_label = "Finish session →" if finishing else "Next question →"

                        nav_col_1, nav_col_2 = st.columns([1, 1])
                        with nav_col_1:
                            if st.button("Leave session", use_container_width=True):
                                st.session_state.practice_phase = "setup"
                                st.session_state.answer_submitted = False
                                st.rerun()
                        with nav_col_2:
                            if st.button(
                                next_label,
                                type="primary",
                                use_container_width=True,
                            ):
                                if finishing:
                                    finalize_session()
                                else:
                                    nxt = pick_next(
                                        config,
                                        st.session_state.session_used_ids,
                                        st.session_state.current_difficulty,
                                    )
                                    if nxt is None:
                                        finalize_session()
                                    else:
                                        st.session_state.current_q = nxt
                                        st.session_state.question_start = time.time()
                                        st.session_state.answer_submitted = False
                                        st.session_state.session_last_answer = None
                                        st.session_state.session_last_correct = None
                                st.rerun()

            with context_col:
                with st.container(border=True):
                    render_html(
                        """
                        <div class="card-title">Session pulse</div>
                        <div class="card-subtitle">Live signals from your performance</div>
                        """
                    )

                    metric_card(
                        "Current difficulty",
                        st.session_state.current_difficulty.title(),
                        "Adjusts after each answer",
                        "◇",
                    )

                    st.write("")

                    session_answered = st.session_state.session_answered
                    session_correct = st.session_state.session_correct
                    session_acc = (
                        session_correct / session_answered
                        if session_answered else 0.0
                    )

                    st.markdown("**Session accuracy**")
                    st.progress(session_acc)
                    st.caption(
                        f"{session_correct}/{session_answered} correct this session"
                    )

                    est = question.get("estimated_seconds")
                    if est and st.session_state.show_timing:
                        st.markdown("**Suggested time**")
                        st.caption(f"About {est} seconds for this question")

                st.write("")

                render_html(
                    """
                    <div class="coach-quote">
                        Take ten seconds to identify what the question is really
                        testing before calculating.
                    </div>
                    """
                )

        # ---------------- SUMMARY ----------------
        elif phase == "summary":
            answered = st.session_state.session_answered
            correct = st.session_state.session_correct
            session_acc = round(correct / answered * 100) if answered else 0
            minutes = st.session_state.session_seconds / 60

            section_header(
                "Session complete",
                "Nice work — here's how it went",
                "Every answer has been folded into your overall progress.",
            )

            summary_cols = st.columns(3)
            with summary_cols[0]:
                metric_card("Questions", answered, "answered this session", "◇")
            with summary_cols[1]:
                metric_card("Accuracy", f"{session_acc}%",
                            f"{correct} of {answered} correct", "✓")
            with summary_cols[2]:
                metric_card("Time", f"{minutes:.1f} min",
                            "focused practice", "◷")

            if session_acc >= 80:
                verdict = (
                    "Strong session. You're handling this difficulty comfortably — "
                    "consider nudging the starting difficulty up next time."
                )
            elif session_acc >= 55:
                verdict = (
                    "Solid, steady work. Keep sessions like this consistent and "
                    "the accuracy will compound."
                )
            else:
                verdict = (
                    "A tougher round — that's where the learning is. Reviewing the "
                    "explanations for the ones you missed is the highest-value move now."
                )

            # AI review of the whole session (cached per completed session so it
            # is generated once, not on every rerun). Falls back to the verdict.
            review_text = verdict
            if st.session_state.get("ai_enabled"):
                review_cache = st.session_state.setdefault("ai_review_cache", {})
                session_id = st.session_state.sessions_completed
                if session_id not in review_cache:
                    session_entries = (
                        st.session_state.history[-answered:] if answered else []
                    )
                    with st.spinner("Sam is reviewing your session…"):
                        review_cache[session_id] = ai_session_review(session_entries)
                ok, ai_review = review_cache[session_id]
                if ok and ai_review:
                    review_text = ai_review

            render_html(
                f"""
                <div class="ai-insight">
                    <div class="ai-insight-label">Sam's read</div>
                    <h3>Where you landed</h3>
                    <p>{to_html_block(review_text)}</p>
                </div>
                """
            )

            action_cols = st.columns([1, 1])
            with action_cols[0]:
                if st.button("Start a new session", type="primary",
                             use_container_width=True):
                    st.session_state.practice_phase = "setup"
                    st.rerun()
            with action_cols[1]:
                if st.button("Back to home", use_container_width=True):
                    st.session_state.practice_phase = "setup"
                    go_to("Home")


# ============================================================
# INSIGHTS PAGE
# ============================================================

elif page == "Insights":
    history = st.session_state.history
    has_data = len(history) > 0
    stats = skill_stats(history)

    section_header(
        "Learning intelligence",
        "Your progress has a pattern",
        "SATSam combines accuracy, pacing, and mistake type across your answers.",
    )

    math_score = _section_scaled(history, "math")
    rw_score = _section_scaled(history, "reading_writing")

    # Pacing: share of questions answered within their suggested time.
    timed = [e for e in history if e.get("est")]
    if timed:
        pace = round(
            100 * sum(1 for e in timed if e["seconds"] <= e["est"]) / len(timed)
        )
    else:
        pace = None

    metrics = st.columns(4)

    with metrics[0]:
        metric_card(
            "Predicted score",
            st.session_state.predicted_score if has_data else "—",
            "Estimated from your answers" if has_data else "Awaiting data",
            "↗",
        )
    with metrics[1]:
        metric_card(
            "Math",
            math_score if math_score is not None else "—",
            "Section estimate (200–800)",
            "∑",
        )
    with metrics[2]:
        metric_card(
            "Reading & Writing",
            rw_score if rw_score is not None else "—",
            "Section estimate (200–800)",
            "Aa",
        )
    with metrics[3]:
        metric_card(
            "Pacing",
            f"{pace}%" if pace is not None else "—",
            "Answered within suggested time",
            "◷",
        )

    section_header(
        "Score trajectory",
        "How your estimate is moving",
        "Your projection updates as SATSam gathers more evidence.",
    )

    chart_col, summary_col = st.columns([1.65, 0.85], gap="large")

    with chart_col:
        with st.container(border=True):
            trajectory = list(st.session_state.score_history)
            # Include the live estimate as the latest point.
            if has_data and (not trajectory or trajectory[-1] != st.session_state.predicted_score):
                trajectory = trajectory + [st.session_state.predicted_score]

            if trajectory:
                st.line_chart(
                    {
                        "Predicted score": trajectory,
                        "Target score": [st.session_state.target_score] * len(trajectory),
                    },
                    height=330,
                )
                st.caption(
                    "Each point marks your predicted score after a completed session."
                )
            else:
                empty_state(
                    "Complete a practice session and your score trajectory will "
                    "start plotting here."
                )

    with summary_col:
        if has_data:
            diagnosis = (
                f"You're averaging {accuracy()}% across "
                f"{st.session_state.questions_solved} questions."
            )
            if math_score is not None and rw_score is not None:
                if math_score >= rw_score:
                    diagnosis += " Math is currently your stronger section."
                else:
                    diagnosis += " Reading and Writing is currently your stronger section."
        else:
            diagnosis = (
                "Once you've answered some questions, SATSam will diagnose which "
                "section and skills are driving your score."
            )

        render_html(
            f"""
            <div class="ai-insight">
                <div class="ai-insight-label">Weekly diagnosis</div>
                <h3>Where you stand</h3>
                <p>{esc(diagnosis)}</p>
            </div>
            """
        )

        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Score opportunity</div>
                <div class="card-subtitle">
                    Estimated points available toward your target
                </div>
                """
            )

            gap = max(0, st.session_state.target_score - st.session_state.predicted_score) if has_data else 0
            st.metric(
                "Gap to target",
                f"+{gap} points" if has_data else "—",
                "with current consistency" if has_data else "answer questions to estimate",
            )

            prep = prep_window_percent() / 100
            st.progress(prep)
            st.caption(
                f"You're {round(prep * 100)}% through your preparation window."
            )

    section_header(
        "Skill map",
        "Where your next points are hiding",
        "Ranked by your accuracy on each skill you've practiced.",
    )

    weak_col, strong_col = st.columns(2, gap="large")

    ranked = sorted(stats.items(), key=lambda kv: kv[1]["acc"])

    with weak_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Highest-impact opportunities</div>
                <div class="card-subtitle">Skills worth prioritizing next</div>
                """
            )
            weak_list = [item for item in ranked if item[1]["acc"] < 80][:3]
            if weak_list:
                for skill, record in weak_list:
                    topic_row(skill, record["acc"], status_for_accuracy(record["acc"]))
            elif stats:
                empty_state("No weak spots yet — everything you've practiced is at 80% or above.")
            else:
                empty_state("Practice a few questions to reveal your weakest skills.")

    with strong_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Reliable strengths</div>
                <div class="card-subtitle">Skills you can trust under time pressure</div>
                """
            )
            strong_list = [item for item in reversed(ranked) if item[1]["acc"] >= 80][:3]
            if strong_list:
                for skill, record in strong_list:
                    topic_row(skill, record["acc"], status_for_accuracy(record["acc"]))
            elif stats:
                empty_state("No skill has reached 80% yet — keep practicing to build reliable strengths.")
            else:
                empty_state("Practice a few questions to reveal your strongest skills.")


# ============================================================
# STUDY PLAN PAGE
# ============================================================

elif page == "Study Plan":
    section_header(
        "Personalized planning",
        "Build a plan that fits real life",
        "SATSam balances urgency, weak areas, and available study time.",
    )

    settings_col, preview_col = st.columns([0.9, 1.5], gap="large")

    with settings_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Plan preferences</div>
                <div class="card-subtitle">Set realistic boundaries for your week</div>
                """
            )

            st.date_input("SAT date", key="sat_date")

            st.number_input(
                "Target score",
                min_value=400,
                max_value=1600,
                step=10,
                key="target_score",
            )

            weekday_minutes = st.slider(
                "Weekday minutes",
                min_value=15,
                max_value=120,
                step=5,
                key="weekday_minutes",
                value=45,
            )

            weekend_minutes = st.slider(
                "Weekend minutes",
                min_value=30,
                max_value=240,
                step=15,
                key="weekend_minutes",
                value=120,
            )

            st.selectbox(
                "Preferred lighter day",
                ["Friday", "Sunday", "Wednesday", "No lighter day"],
                key="rest_day",
            )

            plan_button_label = (
                "Generate my plan with Sam"
                if st.session_state.get("ai_enabled")
                else "Regenerate my plan"
            )
            if st.button(
                plan_button_label,
                type="primary",
                use_container_width=True,
            ):
                if st.session_state.get("ai_enabled"):
                    with st.spinner("Sam is building your week…"):
                        ok, result = ai_generate_study_plan()
                    if ok:
                        st.session_state.ai_study_plan = result
                        try:
                            save_settings()
                        except OSError as error:
                            st.warning(
                                f"Plan generated, but it couldn't be saved: {error}"
                            )
                        st.success(
                            "Sam built a plan around your goals and weak spots."
                        )
                    else:
                        st.error(f"Couldn't generate a plan: {result}")
                else:
                    st.success("Your plan was updated around your available time.")

            if st.session_state.get("ai_study_plan"):
                if st.button("Clear AI plan", use_container_width=True):
                    st.session_state.ai_study_plan = None
                    try:
                        save_settings()
                    except OSError:
                        pass
                    st.rerun()

    with preview_col:
        ai_plan = st.session_state.get("ai_study_plan")

        if ai_plan:
            strategy = ai_plan.get("strategy") or ai_plan.get("weekly_focus") or (
                "A plan built around your current weak spots and available time."
            )
            render_html(
                f"""
                <div class="ai-insight">
                    <div class="ai-insight-label">Sam's plan strategy</div>
                    <h3>Your personalized week</h3>
                    <p>{to_html_block(strategy)}</p>
                </div>
                """
            )

            days = ai_plan.get("days") or []
            plan_left, plan_right = st.columns(2)
            for index, day in enumerate(days):
                if not isinstance(day, dict):
                    continue
                target_col = plan_left if index % 2 == 0 else plan_right
                name = esc(day.get("day", f"Day {index + 1}"))
                minutes = day.get("minutes")
                minutes_label = f" · {esc(minutes)} min" if minutes else ""
                task = esc(day.get("task") or day.get("focus") or "Study block")
                detail = esc(day.get("detail") or day.get("focus") or "")
                with target_col:
                    render_html(
                        f"""
                        <div class="day-card">
                            <div class="day-name">{name}{minutes_label}</div>
                            <div class="day-task">{task}</div>
                            <div class="day-detail">{detail}</div>
                        </div>
                        """
                    )

            weekly_focus = ai_plan.get("weekly_focus")
            if weekly_focus:
                render_html(
                    f'<div class="coach-quote">{to_html_block(weekly_focus)}</div>'
                )

            st.caption(
                "This plan is saved with your preferences. Regenerate it whenever "
                "your performance or schedule changes."
            )

        else:
            light_day = round(weekday_minutes * 0.55 / 5) * 5
            weekly_total = (weekday_minutes * 4) + light_day + weekend_minutes + 90

            render_html(
                """
                <div class="ai-insight">
                    <div class="ai-insight-label">Plan strategy</div>
                    <h3>Prioritize math without neglecting reading.</h3>
                    <p>
                        This week allocates 55% of practice to math because it
                        currently offers the largest point return. Reading remains
                        frequent enough to preserve momentum.
                    </p>
                </div>
                """
            )

            plan_left, plan_right = st.columns(2)

            with plan_left:
                render_html(
                    f"""
                    <div class="day-card">
                        <div class="day-name">Monday · {weekday_minutes} min</div>
                        <div class="day-task">Linear equations + guided practice</div>
                        <div class="day-detail">8-minute lesson · 15 adaptive questions</div>
                    </div>
                    <div class="day-card">
                        <div class="day-name">Tuesday · {weekday_minutes} min</div>
                        <div class="day-task">Reading inference and evidence</div>
                        <div class="day-detail">Two short passages · Mistake reflection</div>
                    </div>
                    <div class="day-card">
                        <div class="day-name">Wednesday · {weekday_minutes} min</div>
                        <div class="day-task">Timed mixed math module</div>
                        <div class="day-detail">Test pacing · Calculator strategy</div>
                    </div>
                    <div class="day-card">
                        <div class="day-name">Thursday · {weekday_minutes} min</div>
                        <div class="day-task">Grammar precision</div>
                        <div class="day-detail">Transitions · Sentence boundaries</div>
                    </div>
                    """
                )

            with plan_right:
                render_html(
                    f"""
                    <div class="day-card">
                        <div class="day-name">Friday · {light_day} min</div>
                        <div class="day-task">Light review and confidence set</div>
                        <div class="day-detail">Saved mistakes · Five mastered questions</div>
                    </div>
                    <div class="day-card">
                        <div class="day-name">Saturday · {weekend_minutes} min</div>
                        <div class="day-task">Full-length practice modules</div>
                        <div class="day-detail">Timed conditions · Automated analysis</div>
                    </div>
                    <div class="day-card">
                        <div class="day-name">Sunday · 90 min</div>
                        <div class="day-task">Deep mistake review</div>
                        <div class="day-detail">Diagnose patterns · Update next week's plan</div>
                    </div>
                    <div class="day-card">
                        <div class="day-name">Weekly outcome</div>
                        <div class="day-task">{weekly_total} focused minutes</div>
                        <div class="day-detail">105 questions · 2 timed modules</div>
                    </div>
                    """
                )


# ============================================================
# FOCUS TIMER PAGE
# ============================================================

elif page == "Focus Timer":
    section_header(
        "Distraction-free study",
        "One focused block at a time",
        "Use a quiet timer for practice, review, or full modules.",
    )

    timer_col, intention_col = st.columns([1.25, 0.75], gap="large")

    with timer_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Focus session</div>
                <div class="card-subtitle">
                    Stay with one clear task until the timer ends
                </div>
                """
            )

            timer_length = st.slider(
                "Session length",
                min_value=5,
                max_value=60,
                value=25,
                step=5,
                key="timer_length",
            )

            timer_seconds = timer_length * 60

            timer_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">

                <style>
                    * {{
                        box-sizing: border-box;
                    }}

                    body {{
                        margin: 0;
                        padding: 0;
                        background: transparent;
                        font-family: Arial, sans-serif;
                        color: #28241F;
                    }}

                    .timer-shell {{
                        width: 100%;
                        padding: 22px 18px 10px 18px;
                        text-align: center;
                    }}

                    .timer-ring {{
                        width: 230px;
                        height: 230px;
                        margin: 0 auto;
                        position: relative;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}

                    .timer-ring svg {{
                        position: absolute;
                        width: 230px;
                        height: 230px;
                        transform: rotate(-90deg);
                    }}

                    .timer-ring circle {{
                        fill: none;
                        stroke-width: 10;
                    }}

                    .ring-background {{
                        stroke: #E9DFD4;
                    }}

                    .ring-progress {{
                        stroke: #C9694A;
                        stroke-linecap: round;
                        transition: stroke-dashoffset 0.3s linear;
                    }}

                    .timer-content {{
                        position: relative;
                        z-index: 2;
                    }}

                    .time-display {{
                        font-family: Georgia, serif;
                        font-size: 48px;
                        font-weight: 600;
                        letter-spacing: -1px;
                        color: #28241F;
                    }}

                    .timer-status {{
                        margin-top: 7px;
                        font-size: 13px;
                        font-weight: 600;
                        color: #746D63;
                    }}

                    .button-row {{
                        display: grid;
                        grid-template-columns: 1fr 1fr 1fr;
                        gap: 10px;
                        max-width: 520px;
                        margin: 24px auto 0 auto;
                    }}

                    button {{
                        min-height: 44px;
                        border-radius: 12px;
                        border: 1px solid #E6DDD1;
                        font-size: 13px;
                        font-weight: 700;
                        cursor: pointer;
                        transition:
                            transform 0.15s ease,
                            background 0.15s ease;
                    }}

                    button:hover {{
                        transform: translateY(-1px);
                    }}

                    .start-button {{
                        color: white;
                        background: #C9694A;
                        border-color: #C9694A;
                    }}

                    .start-button:hover {{
                        background: #A95036;
                    }}

                    .pause-button,
                    .reset-button {{
                        color: #28241F;
                        background: #FFFDF8;
                    }}

                    .pause-button:hover,
                    .reset-button:hover {{
                        background: #F7EFE6;
                    }}

                    .session-message {{
                        min-height: 22px;
                        margin-top: 18px;
                        font-size: 13px;
                        font-weight: 600;
                        color: #6F856F;
                    }}

                    .tip {{
                        max-width: 520px;
                        margin: 16px auto 0 auto;
                        padding: 13px 15px;
                        border-radius: 12px;
                        background: #F5E7BC;
                        color: #705D34;
                        font-size: 12px;
                        line-height: 1.5;
                        text-align: left;
                    }}

                    @media (max-width: 520px) {{
                        .timer-ring,
                        .timer-ring svg {{
                            width: 190px;
                            height: 190px;
                        }}

                        .time-display {{
                            font-size: 40px;
                        }}

                        .button-row {{
                            grid-template-columns: 1fr;
                        }}
                    }}
                </style>
            </head>

            <body>
                <div class="timer-shell">
                    <div class="timer-ring">
                        <svg viewBox="0 0 240 240">
                            <circle
                                class="ring-background"
                                cx="120"
                                cy="120"
                                r="104"
                            ></circle>

                            <circle
                                id="progressCircle"
                                class="ring-progress"
                                cx="120"
                                cy="120"
                                r="104"
                            ></circle>
                        </svg>

                        <div class="timer-content">
                            <div id="timeDisplay" class="time-display">
                                {timer_length}:00
                            </div>

                            <div id="timerStatus" class="timer-status">
                                Ready to focus
                            </div>
                        </div>
                    </div>

                    <div class="button-row">
                        <button
                            id="startButton"
                            class="start-button"
                            onclick="startTimer()"
                        >
                            Start
                        </button>

                        <button
                            id="pauseButton"
                            class="pause-button"
                            onclick="pauseTimer()"
                        >
                            Pause
                        </button>

                        <button
                            class="reset-button"
                            onclick="resetTimer()"
                        >
                            Reset
                        </button>
                    </div>

                    <div
                        id="sessionMessage"
                        class="session-message"
                    ></div>

                    <div class="tip">
                        Keep only the materials needed for this session open.
                        When the timer ends, take a short break before starting
                        another focused block.
                    </div>
                </div>

                                <script>
                    const storageKey = "satsam_focus_timer_v2";
                    const selectedDuration = {timer_seconds};

                    const timeDisplay =
                        document.getElementById("timeDisplay");

                    const timerStatus =
                        document.getElementById("timerStatus");

                    const sessionMessage =
                        document.getElementById("sessionMessage");

                    const startButton =
                        document.getElementById("startButton");

                    const progressCircle =
                        document.getElementById("progressCircle");

                    const radius = 104;
                    const circumference = 2 * Math.PI * radius;

                    progressCircle.style.strokeDasharray =
                        circumference;

                    let timerInterval = null;

                    let timerState = {{
                        duration: selectedDuration,
                        remaining: selectedDuration,
                        running: false,
                        completed: false,
                        endTime: null
                    }};


                    // -------------------------------------------------
                    // LOCAL STORAGE
                    // -------------------------------------------------

                    function saveState() {{
                        localStorage.setItem(
                            storageKey,
                            JSON.stringify(timerState)
                        );
                    }}


                    function loadState() {{
                        const savedState =
                            localStorage.getItem(storageKey);

                        if (!savedState) {{
                            saveState();
                            return;
                        }}

                        try {{
                            const parsedState =
                                JSON.parse(savedState);

                            timerState = {{
                                duration:
                                    Number(parsedState.duration)
                                    || selectedDuration,

                                remaining:
                                    Number(parsedState.remaining)
                                    || selectedDuration,

                                running:
                                    Boolean(parsedState.running),

                                completed:
                                    Boolean(parsedState.completed),

                                endTime:
                                    parsedState.endTime
                                    ? Number(parsedState.endTime)
                                    : null
                            }};

                            /*
                            If no session is active and the user changes
                            the Streamlit duration slider, use the newly
                            selected duration.
                            */
                            if (
                                !timerState.running
                                && !timerState.completed
                                && timerState.remaining
                                    === timerState.duration
                                && timerState.duration
                                    !== selectedDuration
                            ) {{
                                timerState.duration =
                                    selectedDuration;

                                timerState.remaining =
                                    selectedDuration;

                                timerState.endTime = null;

                                saveState();
                            }}

                        }} catch (error) {{
                            console.log(
                                "Could not restore timer state.",
                                error
                            );

                            timerState = {{
                                duration: selectedDuration,
                                remaining: selectedDuration,
                                running: false,
                                completed: false,
                                endTime: null
                            }};

                            saveState();
                        }}
                    }}


                    // -------------------------------------------------
                    // TIME CALCULATIONS
                    // -------------------------------------------------

                    function calculateRemainingTime() {{
                        if (
                            timerState.running
                            && timerState.endTime
                        ) {{
                            timerState.remaining = Math.max(
                                0,
                                Math.ceil(
                                    (
                                        timerState.endTime
                                        - Date.now()
                                    ) / 1000
                                )
                            );
                        }}

                        return timerState.remaining;
                    }}


                    function formatTime(totalSeconds) {{
                        const safeSeconds =
                            Math.max(0, totalSeconds);

                        const minutes =
                            Math.floor(safeSeconds / 60);

                        const seconds =
                            safeSeconds % 60;

                        return (
                            String(minutes).padStart(2, "0")
                            + ":"
                            + String(seconds).padStart(2, "0")
                        );
                    }}


                    // -------------------------------------------------
                    // DISPLAY
                    // -------------------------------------------------

                    function updateDisplay() {{
                        const remaining =
                            calculateRemainingTime();

                        timeDisplay.textContent =
                            formatTime(remaining);

                        const duration =
                            Math.max(timerState.duration, 1);

                        const elapsed =
                            duration - remaining;

                        const progress =
                            Math.min(
                                Math.max(elapsed / duration, 0),
                                1
                            );

                        progressCircle.style.strokeDashoffset =
                            circumference * progress;

                        if (timerState.completed) {{
                            timerStatus.textContent =
                                "Session complete";

                            sessionMessage.textContent =
                                "Excellent work. Take a short, "
                                + "intentional break.";

                            startButton.textContent =
                                "Complete";

                        }} else if (timerState.running) {{
                            timerStatus.textContent =
                                "Focus in progress";

                            sessionMessage.textContent = "";

                            startButton.textContent =
                                "Running";

                        }} else if (
                            timerState.remaining
                            < timerState.duration
                        ) {{
                            timerStatus.textContent =
                                "Session paused";

                            sessionMessage.textContent = "";

                            startButton.textContent =
                                "Resume";

                        }} else {{
                            timerStatus.textContent =
                                "Ready to focus";

                            sessionMessage.textContent = "";

                            startButton.textContent =
                                "Start";
                        }}
                    }}


                    // -------------------------------------------------
                    // TIMER CONTROLS
                    // -------------------------------------------------

                    function startTimer() {{
                        if (
                            timerState.running
                            || timerState.completed
                            || timerState.remaining <= 0
                        ) {{
                            return;
                        }}

                        timerState.running = true;

                        timerState.endTime =
                            Date.now()
                            + timerState.remaining * 1000;

                        saveState();
                        updateDisplay();
                        beginInterval();
                    }}


                    function pauseTimer() {{
                        if (!timerState.running) {{
                            return;
                        }}

                        calculateRemainingTime();

                        timerState.running = false;
                        timerState.endTime = null;

                        clearTimerInterval();
                        saveState();
                        updateDisplay();
                    }}


                    function resetTimer() {{
                        clearTimerInterval();

                        timerState = {{
                            duration: selectedDuration,
                            remaining: selectedDuration,
                            running: false,
                            completed: false,
                            endTime: null
                        }};

                        saveState();
                        updateDisplay();
                    }}


                    function completeTimer(
                        playSound = true
                    ) {{
                        clearTimerInterval();

                        timerState.remaining = 0;
                        timerState.running = false;
                        timerState.completed = true;
                        timerState.endTime = null;

                        saveState();
                        updateDisplay();

                        if (playSound) {{
                            playCompletionSound();
                        }}
                    }}


                    // -------------------------------------------------
                    // INTERVAL MANAGEMENT
                    // -------------------------------------------------

                    function clearTimerInterval() {{
                        if (timerInterval !== null) {{
                            clearInterval(timerInterval);
                            timerInterval = null;
                        }}
                    }}


                    function beginInterval() {{
                        clearTimerInterval();

                        timerInterval = setInterval(() => {{
                            const remaining =
                                calculateRemainingTime();

                            if (remaining <= 0) {{
                                completeTimer(true);
                                return;
                            }}

                            /*
                            Save periodically so the paused value is
                            always accurate if the iframe disappears.
                            */
                            saveState();
                            updateDisplay();

                        }}, 250);
                    }}


                    // -------------------------------------------------
                    // COMPLETION SOUND
                    // -------------------------------------------------

                    function playCompletionSound() {{
                        try {{
                            const AudioContextClass =
                                window.AudioContext
                                || window.webkitAudioContext;

                            const audioContext =
                                new AudioContextClass();

                            const oscillator =
                                audioContext.createOscillator();

                            const gainNode =
                                audioContext.createGain();

                            oscillator.connect(gainNode);
                            gainNode.connect(
                                audioContext.destination
                            );

                            oscillator.frequency.value = 660;
                            oscillator.type = "sine";

                            gainNode.gain.setValueAtTime(
                                0.14,
                                audioContext.currentTime
                            );

                            gainNode.gain
                                .exponentialRampToValueAtTime(
                                    0.001,
                                    audioContext.currentTime + 1.2
                                );

                            oscillator.start();

                            oscillator.stop(
                                audioContext.currentTime + 1.2
                            );

                        }} catch (error) {{
                            console.log(
                                "Completion sound unavailable.",
                                error
                            );
                        }}
                    }}


                    // -------------------------------------------------
                    // RESTORE THE TIMER WHEN PAGE REOPENS
                    // -------------------------------------------------

                    loadState();

                    if (
                        timerState.running
                        && timerState.endTime
                    ) {{
                        calculateRemainingTime();

                        /*
                        The timer may have finished while the user was
                        on another SATSam page.
                        */
                        if (timerState.remaining <= 0) {{
                            completeTimer(false);
                        }} else {{
                            saveState();
                            updateDisplay();
                            beginInterval();
                        }}
                    }} else {{
                        updateDisplay();
                    }}


                    /*
                    Keep the saved time accurate if the browser tab is
                    hidden or restored.
                    */
                    document.addEventListener(
                        "visibilitychange",
                        () => {{
                            if (
                                document.visibilityState === "visible"
                            ) {{
                                if (
                                    timerState.running
                                    && timerState.endTime
                                ) {{
                                    calculateRemainingTime();

                                    if (
                                        timerState.remaining <= 0
                                    ) {{
                                        completeTimer(false);
                                    }} else {{
                                        updateDisplay();
                                        beginInterval();
                                    }}
                                }}
                            }}
                        }}
                    );
                </script>
            </body>
            </html>
            """

            components.html(
                timer_html,
                height=430,
                scrolling=False,
            )

            st.caption(
    "The timer continues while you use other SATSam pages. "
    "Press Reset before changing the duration of an active session."
)

    with intention_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Set an intention</div>
                <div class="card-subtitle">
                    Decide exactly what you will accomplish
                </div>
                """
            )

            focus_activity = st.selectbox(
                "Focus activity",
                [
                    "Adaptive practice",
                    "Mistake review",
                    "Concept lesson",
                    "Timed module",
                    "Reading practice",
                    "Math practice",
                ],
                key="focus_activity",
            )

            session_intention = st.text_area(
                "Session intention",
                placeholder=(
                    "Example: I will carefully verify every "
                    "substitution step before selecting an answer."
                ),
                height=135,
                key="session_intention",
            )

            distraction_mode = st.toggle(
                "Distraction-free reminder",
                value=True,
                key="distraction_mode",
            )

            if distraction_mode:
                render_html(
                    """
                    <div class="ai-insight">
                        <div class="ai-insight-label">
                            Before you begin
                        </div>
                        <h3>Prepare your environment.</h3>
                        <p>
                            Silence notifications, close unrelated tabs,
                            place your phone out of reach, and keep water
                            nearby.
                        </p>
                    </div>
                    """
                )

            if session_intention.strip():
                render_html(
                    f"""
                    <div class="coach-quote">
                        Your commitment: {session_intention}
                    </div>
                    """
                )
            else:
                render_html(
                    """
                    <div class="coach-quote">
                        A clear intention makes it easier to notice when
                        your attention begins to drift.
                    </div>
                    """
                )


# ============================================================
# SETTINGS PAGE
# ============================================================

elif page == "Settings":
    section_header(
        "Preferences",
        "Make SATSam feel like your study space",
        "These settings save to a local file and drive how sessions and the "
        "AI tutor behave.",
    )

    settings_left, settings_right = st.columns(2, gap="large")

    # ---------------- Session defaults ----------------
    with settings_left:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Targets &amp; session defaults</div>
                <div class="card-subtitle">
                    Pre-fill every new practice session and set your score goal
                </div>
                """
            )

            st.slider(
                "Daily study goal (minutes)",
                min_value=15,
                max_value=120,
                step=5,
                key="study_goal",
            )

            st.number_input(
                "Target SAT score",
                min_value=400,
                max_value=1600,
                step=10,
                key="target_score",
            )

            st.selectbox(
                "Default subject",
                [
                    "SATSam recommendation",
                    "Balanced",
                    "Math",
                    "Reading and Writing",
                ],
                key="default_practice_subject",
            )

            st.selectbox(
                "Default starting difficulty",
                ["Foundation", "Standard", "Challenging", "Test-level"],
                key="default_start_difficulty",
            )

            st.slider(
                "Default questions per session",
                min_value=5,
                max_value=30,
                step=1,
                key="default_practice_count",
            )

            st.toggle(
                "Explain each answer immediately",
                key="auto_explain",
            )

            st.toggle(
                "Show timing guidance during practice",
                key="show_timing",
            )

    # ---------------- AI tutor ----------------
    with settings_right:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">AI tutor</div>
                <div class="card-subtitle">
                    Connect a local Ollama model for custom explanations
                </div>
                """
            )

            st.toggle(
                "Enable the AI tutor",
                key="ai_enabled",
                help="Turn on once your local Ollama model is running.",
            )

            st.text_input(
                "Ollama host",
                key="ai_host",
                placeholder="http://localhost:11434",
            )

            st.text_input(
                "Model name",
                key="ai_model",
                placeholder="e.g. qwen3:8b",
                help="Run `ollama pull qwen3:8b` first. The very first response "
                     "after launch is slow while the model loads into memory.",
            )

            st.slider(
                "Response creativity (temperature)",
                min_value=0.0,
                max_value=1.0,
                step=0.1,
                key="ai_temperature",
            )

            st.selectbox(
                "Explanation style",
                [
                    "Concise and strategic",
                    "Step-by-step",
                    "Socratic questions",
                    "Detailed tutor mode",
                ],
                key="explanation_style",
            )

            st.selectbox(
                "Coach personality",
                [
                    "Warm and focused",
                    "Direct and challenging",
                    "Calm and encouraging",
                ],
                key="coach_personality",
            )

            st.toggle(
                "Offer AI hints before revealing the answer",
                key="ai_hints",
            )

            if st.button("Test connection", use_container_width=True):
                host = st.session_state.get("ai_host") or "http://localhost:11434"
                reachable, detail = ollama_reachable(host)
                if reachable and detail:
                    st.success("Connected. Models available: " + ", ".join(detail))
                elif reachable:
                    st.warning("Connected, but no models are installed yet.")
                else:
                    st.error(f"Could not reach Ollama: {detail}")

    # ---------------- Prompt preview ----------------
    with st.container(border=True):
        render_html(
            """
            <div class="card-title">How Sam will sound</div>
            <div class="card-subtitle">
                The instructions sent to your local model, built from the two
                settings above
            </div>
            """
        )
        render_html(
            f'<div class="stimulus-box">{to_html_block(build_coach_system_prompt())}</div>'
        )

    # ---------------- Data & progress ----------------
    section_header(
        "Your data",
        "Everything stays on your machine",
        "Export a copy of your progress or clear it to start fresh.",
    )

    export_col, reset_col, save_col = st.columns(3)

    with export_col:
        progress_json = json.dumps(
            {
                "history": [
                    {**entry, "ts": entry["ts"].isoformat()}
                    for entry in st.session_state.history
                ],
                "score_history": st.session_state.score_history,
                "sessions_completed": st.session_state.sessions_completed,
                "best_streak": st.session_state.best_streak,
            },
            indent=2,
        )
        st.download_button(
            "Export progress",
            data=progress_json,
            file_name="satsam-progress.json",
            mime="application/json",
            use_container_width=True,
            disabled=not st.session_state.history,
        )

    with reset_col:
        if st.button("Reset my progress", use_container_width=True):
            st.session_state.history = []
            st.session_state.score_history = []
            st.session_state.sessions_completed = 0
            st.session_state.best_streak = 0
            st.session_state.practice_phase = "setup"
            st.session_state.error_fingerprint_cache = {}
            st.session_state.ai_explanations = {}
            recompute_metrics()
            st.success("Your progress has been cleared.")

    with save_col:
        if st.button("Save preferences", type="primary", use_container_width=True):
            try:
                save_settings()
                st.success("Preferences saved to satsam-settings.json.")
            except OSError as error:
                st.warning(f"Could not write settings file: {error}")