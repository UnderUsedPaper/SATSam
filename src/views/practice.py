"""Adaptive practice: session setup, the question loop, and the summary."""

import time
from datetime import datetime

import streamlit as st

from src.ai.coaching import ai_session_review
from src.ai.explanations import get_ai_explanation
from src.ai.fingerprint import (
    fallback_error_fingerprint,
    get_error_fingerprint,
    render_error_fingerprint,
)
from src.components.chat import open_question_chat
from src.components.common import metric_card, section_header
from src.config import START_DIFFICULTY
from src.data_loader import QUESTIONS
from src.html_utils import esc, render_html, to_html_block
from src.questions import check_answer, pick_next, shift_difficulty
from src.state import finalize_session, go_to, start_session


def render():
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
            "the **data/** folder, then refresh."
        )
        return

    phase = st.session_state.practice_phase

    if phase == "setup":
        _render_setup()
    elif phase == "empty":
        _render_empty()
    elif phase == "question":
        _render_question()
    elif phase == "summary":
        _render_summary()


# ---------------- SETUP ----------------

def _render_setup():
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

def _render_empty():
    st.info(
        "No questions matched those filters. Try a broader subject or a "
        "different focus."
    )
    if st.button("Back to setup", type="primary"):
        st.session_state.practice_phase = "setup"
        st.rerun()


# ---------------- QUESTION ----------------

def _render_question():
    question = st.session_state.current_q
    config = st.session_state.session_config
    count = config["count"]
    answered = st.session_state.session_answered
    submitted = st.session_state.answer_submitted

    question_col, context_col = st.columns([1.65, 0.85], gap="large")

    with question_col:
        with st.container(border=True):
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
                _render_answer_input(question, config, count, is_mcq)
            else:
                _render_answer_review(question, config, count, is_mcq)

    with context_col:
        _render_session_pulse(question)


def _render_answer_input(question, config, count, is_mcq):
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


def _render_answer_review(question, config, count, is_mcq):
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
        st.error("Not quite — and that's okay. Sam is looking at the reasoning behind this one.")

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

        if (not last_correct) and is_mcq:
            note = question.get("distractors", {}).get(last_answer)
            if note:
                st.caption(f"Why that option was tempting: {note}")

    # ----- Still confused? Talk it through with Sam -----
    if not last_correct:
        st.write("")
        if st.button(
            "Still not clicking? Talk it through with Sam ✦",
            use_container_width=True,
            key=f"chat_help_{question['id']}",
        ):
            open_question_chat(question, last_answer)
            st.rerun()

    # ----- Advance -----
    finishing = st.session_state.session_answered >= count
    next_label = "Finish session →" if finishing else "Next question →"

    nav_col_1, nav_col_2 = st.columns([1, 1])
    with nav_col_1:
        if st.button("Leave session", use_container_width=True,
                     key="leave_after_answer"):
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


def _render_session_pulse(question):
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

def _render_summary():
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
            "A tougher round — that's exactly where the learning is. "
            "Reviewing the explanations for the ones you missed is the "
            "highest-value move right now."
        )

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
