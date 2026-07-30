"""Study Plan: collect the student's week, then render Sam's generated plan."""

import streamlit as st

from src.ai.study_plan import ai_generate_study_plan
from src.components.common import section_header
from src.config import PLAN_DAYS
from src.html_utils import esc, render_html, to_html_block
from src.settings_store import save_settings


def render():
    section_header(
        "Study plan",
        "A week built around your real life",
        "Tell SATSam how much time you have and what you're working around, "
        "and Sam will shape the week to fit.",
    )

    prefs_col, generate_col = st.columns([1.3, 1], gap="large")

    with prefs_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Your week</div>
                <div class="card-subtitle">
                    These settings decide how much work lands on each day
                </div>
                """
            )

            st.date_input("Test date", key="sat_date")

            st.slider(
                "Target score",
                min_value=400,
                max_value=1600,
                step=10,
                key="target_score",
            )

            st.slider(
                "Weekday study minutes",
                min_value=15,
                max_value=180,
                step=5,
                value=45,
                key="weekday_minutes",
            )

            st.slider(
                "Weekend study minutes",
                min_value=15,
                max_value=240,
                step=5,
                value=120,
                key="weekend_minutes",
            )

            st.selectbox(
                "Preferred lighter day",
                PLAN_DAYS + ["No lighter day"],
                index=6,
                key="rest_day",
                help="Sam will keep this day shorter and lower-pressure.",
            )

    with generate_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">What makes studying hard right now?</div>
                <div class="card-subtitle">
                    Optional, and only ever used to make your plan kinder and more
                    realistic
                </div>
                """
            )

            st.text_area(
                "Your circumstances",
                key="study_circumstances",
                height=120,
                label_visibility="collapsed",
                placeholder=(
                    "e.g. I work weekday evenings, I can't afford prep books, I "
                    "share one laptop with my family, my internet is unreliable."
                ),
            )
            st.caption(
                "Sam treats this as a hard constraint — no expensive tools, "
                "genuinely shorter hard days, and free, offline-friendly practice "
                "wherever possible. This stays on your own device."
            )

            st.write("")

            if st.button(
                "Generate my plan with Sam →",
                type="primary",
                use_container_width=True,
            ):
                if not st.session_state.get("ai_enabled"):
                    st.warning(
                        "The AI tutor is switched off. Turn it on in Settings "
                        "(with your local Ollama model running) to generate a "
                        "personalized plan."
                    )
                else:
                    with st.spinner("Sam is building your week…"):
                        ok, result = ai_generate_study_plan()
                    if ok:
                        st.session_state.ai_study_plan = result
                        try:
                            save_settings()
                        except Exception:
                            pass
                        st.success("Your plan is ready — take a look below.")
                    else:
                        st.error(f"Sam couldn't build a plan: {result}")

    plan = st.session_state.get("ai_study_plan")

    if isinstance(plan, dict) and plan.get("days"):
        _render_generated_plan(plan)
    else:
        _render_starter_framework()


def _render_generated_plan(plan):
    render_html(
        f"""
        <div class="ai-insight" style="margin-top: 1.5rem;">
            <div class="ai-insight-label">Sam's strategy for your week</div>
            <h3>{esc(plan.get("weekly_focus", "Your focus this week"))}</h3>
            <p>{to_html_block(plan.get("strategy", ""))}</p>
        </div>
        """
    )

    for day in plan["days"]:
        blocks_html = ""
        for block in day.get("blocks", []):
            q_badge = (
                f'<span class="plan-block-questions">'
                f'{int(block.get("question_count", 0))} Q</span>'
                if block.get("question_count") else ""
            )
            blocks_html += (
                '<div class="plan-block">'
                f'<div class="plan-block-time">{int(block.get("minutes", 0))}<br>min</div>'
                '<div class="plan-block-content">'
                '<div class="plan-block-header">'
                f'<div class="plan-block-title">{esc(block.get("title", ""))}</div>'
                f'{q_badge}'
                '</div>'
                f'<div class="plan-block-description">{to_html_block(block.get("description", ""))}</div>'
                '</div></div>'
            )

        render_html(
            f"""
            <div class="detailed-day-card">
                <div class="detailed-day-top">
                    <div>
                        <div class="day-name">{esc(day.get("day", ""))}</div>
                        <div class="day-task">{esc(day.get("task", ""))}</div>
                        <div class="plan-focus-label">Focus: {esc(day.get("focus", ""))}</div>
                    </div>
                    <div class="plan-total-badge">{int(day.get("minutes", 0))} min</div>
                </div>
                <div class="plan-rationale">{to_html_block(day.get("rationale", ""))}</div>
                <div class="plan-block-list">{blocks_html}</div>
                <div class="plan-day-footer">
                    <div>Done when: {esc(day.get("completion_check", ""))}</div>
                </div>
            </div>
            """
        )


def _render_starter_framework():
    # Simple starter framework shown before a plan is generated.
    render_html(
        """
        <div class="section-heading" style="margin-top: 2rem;">
            <div class="eyebrow">Starter framework</div>
            <h2>A balanced default week</h2>
            <p>Generate a plan above and Sam will personalize every day for you.</p>
        </div>
        """
    )
    starter = [
        ("Monday", "Algebra foundations", "Warm up on your weakest math skill"),
        ("Tuesday", "Reading & Writing", "Grammar conventions and boundaries"),
        ("Wednesday", "Mixed timed set", "Short adaptive session under time"),
        ("Thursday", "Problem-solving & data", "Charts, ratios, and word problems"),
        ("Friday", "Reading inference", "Evidence and main-idea questions"),
        ("Saturday", "Full practice block", "Longer session + full error review"),
        ("Sunday", "Light review", "Redo missed questions, then rest"),
    ]
    for day_name, task, detail in starter:
        render_html(
            f"""
            <div class="day-card">
                <div class="day-name">{esc(day_name)}</div>
                <div class="day-task">{esc(task)}</div>
                <div class="day-detail">{esc(detail)}</div>
            </div>
            """
        )
