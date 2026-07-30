"""Home dashboard: hero, headline metrics, today's session, and snapshots."""

import streamlit as st

from src.components.common import empty_state, metric_card, section_header, topic_row
from src.helpers import (
    accuracy,
    days_until_sat,
    greeting,
    relative_time,
    status_for_accuracy,
)
from src.html_utils import esc, render_html
from src.metrics import skill_stats, weakest_skills
from src.state import go_to, quick_session_config, start_session


def render():
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
