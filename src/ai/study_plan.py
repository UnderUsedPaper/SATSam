"""Feature 5: the AI-generated study plan.

The model proposes the instructional strategy; SATSam then validates and repairs
the schedule so the workload always adds up to the minutes the student actually
has. Every human-facing field is written directly to the student.
"""

import json
from datetime import datetime

import streamlit as st

from src.ai.client import ollama_chat, parse_json_response
from src.config import OFFICIAL_MODULE_MINUTES, PLAN_DAYS
from src.data_loader import QUESTIONS
from src.helpers import days_until_sat
from src.metrics import skill_stats, weakest_skills


def plan_day_budget(day_name):
    """
    Return the exact user-selected time budget for a day.

    The preferred lighter day receives about 55% of its normal budget,
    rounded to the nearest five minutes.
    """
    is_weekend = day_name in {"Saturday", "Sunday"}

    normal_minutes = int(
        st.session_state.get(
            "weekend_minutes" if is_weekend else "weekday_minutes",
            120 if is_weekend else 45,
        )
    )

    rest_day = st.session_state.get("rest_day", "Sunday")

    if day_name == rest_day and rest_day != "No lighter day":
        minimum = 20 if is_weekend else 15
        lighter_minutes = round((normal_minutes * 0.55) / 5) * 5
        return max(minimum, int(lighter_minutes))

    return normal_minutes


def recent_fingerprint_summary(limit=10):
    """
    Collect recent AI Error Fingerprints without requiring them to exist.
    This safely works with both older and newer history entries.
    """
    patterns = []

    for entry in reversed(st.session_state.get("history", [])):
        fingerprint = entry.get("fingerprint")

        if entry.get("correct") or not isinstance(fingerprint, dict):
            continue

        patterns.append(
            {
                "skill": entry.get("skill", "Unknown skill"),
                "error_type": fingerprint.get("error_label")
                or fingerprint.get("error_type", "Unknown pattern"),
                "micro_skill": fingerprint.get("micro_skill", ""),
                "root_cause": fingerprint.get("root_cause", ""),
                "strategy": fingerprint.get("recommended_strategy", ""),
                "confidence": fingerprint.get("confidence_percent"),
            }
        )

        if len(patterns) >= limit:
            break

    return patterns


def study_plan_performance_context():
    """
    Produce a richer student profile for the planner.

    Accuracy alone is not enough. The model also receives sample size,
    correct/incorrect counts, section, domain, and recent timing.
    """
    history = st.session_state.get("history", [])
    stats = skill_stats(history)

    if not stats:
        return "No practice history yet. Build a balanced diagnostic week."

    lines = []

    for skill, record in sorted(
        stats.items(),
        key=lambda item: (item[1]["acc"], -item[1]["n"]),
    ):
        skill_entries = [
            entry for entry in history if entry.get("skill") == skill
        ]

        recent_entries = skill_entries[-5:]

        average_seconds = (
            round(
                sum(float(entry.get("seconds", 0)) for entry in recent_entries)
                / len(recent_entries)
            )
            if recent_entries
            else 0
        )

        lines.append(
            f"- {skill}: "
            f"{record['c']}/{record['n']} correct "
            f"({record['acc']}% accuracy); "
            f"section={record['section']}; "
            f"domain={record['domain']}; "
            f"recent average time={average_seconds} seconds"
        )

    return "\n".join(lines)


def infer_plan_section(focus, task, blocks=None):
    """Convert model wording into a normalized section identifier."""
    combined = " ".join(
        [
            str(focus or ""),
            str(task or ""),
            json.dumps(blocks or [], default=str),
        ]
    ).lower()

    math_terms = [
        "math", "algebra", "equation", "function", "geometry", "trigonometry",
        "data analysis", "problem-solving", "desmos", "calculator",
    ]

    reading_terms = [
        "reading", "writing", "grammar", "punctuation", "transition",
        "boundaries", "inference", "evidence", "rhetorical", "vocabulary",
        "text structure", "standard english",
    ]

    math_score = sum(term in combined for term in math_terms)
    reading_score = sum(term in combined for term in reading_terms)

    if math_score > reading_score:
        return "math"

    if reading_score > math_score:
        return "reading_writing"

    return "mixed"


def default_focus_for_section(section, weak_skills):
    """Select a reasonable fallback focus when the model omits one."""
    if weak_skills:
        return weak_skills[0]

    if section == "math":
        return "Mixed Math skills"

    if section == "reading_writing":
        return "Mixed Reading and Writing skills"

    return "Balanced SAT practice"


def realistic_blocks_for_day(minutes, section, focus, is_light_day=False):
    """
    Build a time-valid fallback schedule.

    This function is also used whenever the model's blocks are incomplete,
    unrealistic, or do not add up to the displayed daily minutes.
    """
    minutes = max(10, int(minutes))
    focus = str(focus or "priority skills")

    # Very short/light recovery day.
    if minutes <= 25 or is_light_day:
        review_minutes = max(5, round(minutes * 0.35))
        drill_minutes = max(5, minutes - review_minutes)

        return [
            {
                "type": "error_review",
                "minutes": review_minutes,
                "title": "Review recent mistakes",
                "description": (
                    f"Rework missed {focus} questions without looking at the "
                    "answer explanation, then name the rule or reasoning error."
                ),
                "question_count": 0,
            },
            {
                "type": "confidence_drill",
                "minutes": drill_minutes,
                "title": "Short confidence drill",
                "description": (
                    f"Complete a small untimed set on {focus}, prioritizing "
                    "accurate reasoning over speed."
                ),
                "question_count": (
                    max(4, round(drill_minutes / 1.5))
                    if section == "math"
                    else max(5, round(drill_minutes / 1.2))
                ),
            },
        ]

    # A complete official-style module fits naturally.
    module_minutes = OFFICIAL_MODULE_MINUTES.get(section)

    if module_minutes and minutes >= module_minutes + 10:
        remaining = minutes - module_minutes

        preview_minutes = min(8, max(5, remaining // 2))
        review_minutes = remaining - preview_minutes

        question_count = 22 if section == "math" else 27
        section_label = "Math" if section == "math" else "Reading and Writing"

        return [
            {
                "type": "strategy_review",
                "minutes": preview_minutes,
                "title": f"{focus} strategy review",
                "description": (
                    f"Review the key rule, procedure, and common trap for {focus} "
                    "before beginning timed work."
                ),
                "question_count": 0,
            },
            {
                "type": "timed_module",
                "minutes": module_minutes,
                "title": f"Timed {section_label} module",
                "description": (
                    f"Complete one official-length {section_label} module under "
                    "test conditions. Flag uncertain questions instead of pausing."
                ),
                "question_count": question_count,
            },
            {
                "type": "error_review",
                "minutes": review_minutes,
                "title": "Analyze misses and guesses",
                "description": (
                    "Review every incorrect or uncertain response. Record the "
                    "tested skill, error pattern, and one prevention strategy."
                ),
                "question_count": 0,
            },
        ]

    # Normal targeted study block.
    lesson_minutes = min(10, max(6, round(minutes * 0.2)))
    review_minutes = min(12, max(7, round(minutes * 0.22)))
    drill_minutes = minutes - lesson_minutes - review_minutes

    if section == "math":
        question_count = max(6, round(drill_minutes / 1.6))
    elif section == "reading_writing":
        question_count = max(7, round(drill_minutes / 1.2))
    else:
        question_count = max(6, round(drill_minutes / 1.4))

    return [
        {
            "type": "micro_lesson",
            "minutes": lesson_minutes,
            "title": f"Learn the {focus} pattern",
            "description": (
                f"Review the core rule and one worked example for {focus}. "
                "Write down the decision process you should use."
            ),
            "question_count": 0,
        },
        {
            "type": "targeted_drill",
            "minutes": drill_minutes,
            "title": f"Targeted {focus} drill",
            "description": (
                f"Complete approximately {question_count} adaptive questions on "
                f"{focus}. Pause only after submitting each answer."
            ),
            "question_count": question_count,
        },
        {
            "type": "error_review",
            "minutes": review_minutes,
            "title": "Correct and classify mistakes",
            "description": (
                "Redo missed and guessed questions, then record whether each miss "
                "came from knowledge, strategy, execution, or pacing."
            ),
            "question_count": 0,
        },
    ]


def normalize_plan_blocks(raw_blocks, minutes, section, focus, is_light_day=False):
    """
    Validate model-generated timed blocks.

    The AI output is kept only when it contains useful block objects, every block
    has a positive duration, the durations add exactly to the day's displayed
    total, and the workload is not obviously implausible. Otherwise SATSam builds
    a deterministic, realistic replacement.
    """
    if not isinstance(raw_blocks, list) or not raw_blocks:
        return realistic_blocks_for_day(minutes, section, focus, is_light_day)

    cleaned = []

    for block in raw_blocks:
        if not isinstance(block, dict):
            continue

        try:
            block_minutes = int(block.get("minutes", 0))
        except (TypeError, ValueError):
            continue

        if block_minutes <= 0:
            continue

        title = str(
            block.get("title") or block.get("task") or "Study block"
        ).strip()

        description = str(
            block.get("description") or block.get("detail") or ""
        ).strip()

        try:
            question_count = int(block.get("question_count", 0) or 0)
        except (TypeError, ValueError):
            question_count = 0

        cleaned.append(
            {
                "type": str(block.get("type", "practice")),
                "minutes": block_minutes,
                "title": title,
                "description": description,
                "question_count": max(0, question_count),
            }
        )

    total = sum(block["minutes"] for block in cleaned)

    # Reject plans whose displayed work does not fill the stated duration.
    if not cleaned or total != int(minutes):
        return realistic_blocks_for_day(minutes, section, focus, is_light_day)

    # Reject very low workloads such as "2 questions in 45 minutes"
    # unless the block is explicitly a lesson or review block.
    for block in cleaned:
        practice_type = block["type"].lower()
        is_question_block = any(
            term in practice_type
            for term in ["drill", "practice", "module", "timed", "question"]
        )

        if (
            is_question_block
            and block["minutes"] >= 20
            and 0 < block["question_count"] < 6
        ):
            return realistic_blocks_for_day(minutes, section, focus, is_light_day)

    return cleaned


def normalize_study_plan(raw_plan):
    """Convert the model response into a complete and internally consistent plan."""
    if not isinstance(raw_plan, dict):
        raw_plan = {}

    raw_days = raw_plan.get("days")
    if not isinstance(raw_days, list):
        raw_days = []

    raw_day_map = {
        str(day.get("day", "")).strip().lower(): day
        for day in raw_days
        if isinstance(day, dict)
    }

    weak_skills = weakest_skills(st.session_state.get("history", []))
    rest_day = st.session_state.get("rest_day", "Sunday")
    normalized_days = []

    for index, day_name in enumerate(PLAN_DAYS):
        raw_day = raw_day_map.get(day_name.lower())

        if raw_day is None and index < len(raw_days):
            candidate = raw_days[index]
            raw_day = candidate if isinstance(candidate, dict) else {}

        raw_day = raw_day or {}
        minutes = plan_day_budget(day_name)

        focus = str(
            raw_day.get("focus")
            or (weak_skills[index % len(weak_skills)] if weak_skills else "")
        ).strip()

        task = str(raw_day.get("task") or raw_day.get("title") or "").strip()

        raw_blocks = raw_day.get("blocks")
        section = str(raw_day.get("section", "")).lower().strip()

        if section not in {"math", "reading_writing", "mixed"}:
            section = infer_plan_section(focus, task, raw_blocks)

        focus = focus or default_focus_for_section(section, weak_skills)

        is_light_day = day_name == rest_day and rest_day != "No lighter day"

        blocks = normalize_plan_blocks(
            raw_blocks, minutes, section, focus, is_light_day
        )

        actual_total = sum(block["minutes"] for block in blocks)

        total_questions = sum(
            int(block.get("question_count", 0) or 0) for block in blocks
        )

        if not task:
            if any(block["type"] == "timed_module" for block in blocks):
                task = f"Timed module + {focus} review"
            elif is_light_day:
                task = f"Light {focus} recovery"
            else:
                task = f"{focus} mastery session"

        rationale = str(
            raw_day.get("rationale")
            or (
                f"This session targets {focus} because it is currently one of "
                "your highest-priority areas."
            )
        ).strip()

        completion_check = str(
            raw_day.get("completion_check")
            or (
                "Finish every timed block and record the cause of each missed "
                "or guessed question."
            )
        ).strip()

        normalized_days.append(
            {
                "day": day_name,
                "minutes": actual_total,
                "section": section,
                "focus": focus,
                "task": task,
                "rationale": rationale,
                "completion_check": completion_check,
                "question_count": total_questions,
                "blocks": blocks,
            }
        )

    strategy = str(
        raw_plan.get("strategy")
        or (
            "This week combines targeted instruction, realistic timed practice, "
            "and error analysis. Each session is divided into accountable blocks "
            "that fit the time you actually have."
        )
    ).strip()

    weekly_focus = str(
        raw_plan.get("weekly_focus")
        or (
            f"Your highest priority is "
            f"{weak_skills[0] if weak_skills else 'building a balanced baseline'}."
        )
    ).strip()

    return {
        "strategy": strategy,
        "days": normalized_days,
        "weekly_focus": weekly_focus,
        "generated_at": datetime.now().isoformat(),
    }


def ai_generate_study_plan():
    """
    Generate a specific, time-accountable seven-day SAT plan.

    The model proposes the instructional strategy. SATSam then validates and
    repairs the schedule so the workload always matches the displayed minutes.
    """
    history = st.session_state.get("history", [])
    performance = study_plan_performance_context()
    fingerprints = recent_fingerprint_summary()

    weekday_minutes = int(st.session_state.get("weekday_minutes", 45))
    weekend_minutes = int(st.session_state.get("weekend_minutes", 120))
    rest_day = st.session_state.get("rest_day", "Sunday")

    daily_budgets = {day: plan_day_budget(day) for day in PLAN_DAYS}

    score_gap = max(
        0,
        int(st.session_state.target_score)
        - int(st.session_state.predicted_score or 0),
    )

    available_skills = sorted(
        {question.get("skill", "") for question in QUESTIONS} - {""}
    )

    context = {
        "target_score": st.session_state.target_score,
        "current_performance_estimate": (
            st.session_state.predicted_score or "not yet estimated"
        ),
        "score_gap": score_gap,
        "days_until_sat": days_until_sat(),
        "questions_answered": len(history),
        "weekday_minutes": weekday_minutes,
        "weekend_minutes": weekend_minutes,
        "preferred_lighter_day": rest_day,
        "exact_daily_budgets": daily_budgets,
        "performance_by_skill": performance,
        "recent_error_fingerprints": fingerprints,
        "personal_circumstances": (
            (st.session_state.get("study_circumstances") or "").strip()
            or "None shared."
        ),
        "available_question_bank_skills": available_skills,
    }

    system_prompt = """
You are Sam, SATSam's expert and caring instructional planner.

Create realistic digital SAT study schedules. Every recommendation must be
specific, measurable, educationally justified, and possible within the stated
time budget.

Digital SAT timing facts:
- One Reading and Writing module lasts 32 minutes and contains 27 questions.
- One Math module lasts 35 minutes and contains 22 questions.
- Do not call a short drill a full module.
- Do not prescribe a full module unless the day's time budget can fit the
  module plus at least 8 minutes for preparation or review.

Planning rules:
1. Use the exact minutes provided for every day.
2. Break every day into 2 to 4 timed blocks.
3. Block minutes must add exactly to the daily budget.
4. A 40- to 60-minute study day should normally include instruction or strategy
   review, substantial targeted practice, and mistake analysis.
5. Never assign an implausibly tiny workload such as 2 questions for 45 minutes.
6. For Reading and Writing targeted drills, use roughly 1.2 minutes per question.
7. For Math targeted drills, use roughly 1.5 to 1.8 minutes per question.
8. Do not count lesson, review, or reflection time as question-solving time.
9. State the exact skill, question count, timing mode, and review process.
10. Prioritize weaknesses supported by enough evidence, while using diagnostic
    work for skills with very small sample sizes.
11. Use recent Error Fingerprints to address the cause of mistakes, not only
    the content category.
12. Include both Reading and Writing and Math during the week.
13. Make the preferred lighter day genuinely lighter and lower-pressure.
14. Avoid generic descriptions such as "practice reading" or "review math."
15. If the student has shared personal circumstances that make studying harder
    (a job, limited money, caregiving, shared devices, unreliable internet, and
    so on), treat those as HARD CONSTRAINTS. Never assume paid tutors, paid prep
    books, or expensive tools; lean on free and offline-friendly practice, keep
    hard days genuinely short, and keep a compassionate, non-judgmental tone that
    respects everything else they are carrying.
16. Write every human-facing field (strategy, rationale, task, weekly_focus, and
    block descriptions) warmly and directly to the student using "you," like a
    mentor who is on their side and proud of them for showing up. Never clinical.
17. Respond only with valid JSON and no Markdown.
""".strip()

    user_prompt = f"""
STUDENT PROFILE
{json.dumps(context, indent=2, default=str)}

Return exactly this JSON structure:

{{
  "strategy": "Three specific, warm sentences explaining why the week is organized this way for this student.",
  "days": [
    {{
      "day": "Monday",
      "minutes": {daily_budgets["Monday"]},
      "section": "math, reading_writing, or mixed",
      "focus": "An exact SAT skill from the provided question-bank skills",
      "task": "A concise but specific session title",
      "rationale": "Why this work was chosen for you on this day",
      "completion_check": "A measurable condition for finishing the session",
      "blocks": [
        {{
          "type": "micro_lesson, targeted_drill, timed_module, error_review, strategy_review, diagnostic, or confidence_drill",
          "minutes": 8,
          "title": "Specific block title",
          "description": "Detailed instructions including method, timing mode, and intended learning outcome",
          "question_count": 0
        }}
      ]
    }}
  ],
  "weekly_focus": "One specific sentence naming the main weakness, error pattern, and intended outcome."
}}

Requirements:
- Include exactly seven day objects in Monday-to-Sunday order.
- Use these exact daily totals:
{json.dumps(daily_budgets, indent=2)}
- The sum of block minutes inside each day must equal that day's total.
- Use question_count=0 for lessons, review, and reflection.
- Use a positive question_count for drills and modules.
- A Reading and Writing timed module is exactly 32 minutes and 27 questions.
- A Math timed module is exactly 35 minutes and 22 questions.
- Honor the student's personal_circumstances above as hard constraints.
""".strip()

    ok, text = ollama_chat(
        system_prompt, user_prompt, temperature=0.25, force_json=True
    )

    if not ok:
        return False, text

    data = parse_json_response(text)

    if not isinstance(data, dict):
        return False, "The model returned an unexpected format. Please try again."

    normalized_plan = normalize_study_plan(data)

    if len(normalized_plan.get("days", [])) != 7:
        return False, "SATSam could not build all seven study days."

    return True, normalized_plan
