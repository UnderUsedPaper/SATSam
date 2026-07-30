"""Features 3 & 4: session-level coaching.

- ``ai_recommend_focus_skills`` picks which skills to drill next.
- ``ai_session_review`` writes a warm end-of-session note.
"""

from src.ai.client import ollama_chat, parse_json_response
from src.ai.prompts import build_coach_system_prompt
from src.data_loader import QUESTIONS
from src.metrics import skill_stats


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
        "In a warm, encouraging voice, write a short note of about four to six "
        "sentences directly to the student. Celebrate something specific they did "
        "well, gently name the one or two skills worth focusing on next, and end with "
        "one concrete, doable next step. Sound like a mentor who believes in them, "
        "not a report. Avoid Markdown headers."
    )
    return ollama_chat(build_coach_system_prompt(), user_prompt, temperature=0.5)
