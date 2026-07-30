"""Settings: session defaults, Sam's local-model config, and data controls."""

import json

import streamlit as st

from src.ai.client import ollama_reachable
from src.components.common import section_header
from src.config import COACH_PERSONALITY_GUIDANCE, COACH_STYLE_GUIDANCE
from src.html_utils import render_html
from src.settings_store import save_settings


def render():
    section_header(
        "Settings",
        "Tune SATSam to fit you",
        "Your preferences are saved on your own device.",
    )

    defaults_col, ai_col = st.columns(2, gap="large")

    with defaults_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Session defaults</div>
                <div class="card-subtitle">Used to pre-fill new practice sessions</div>
                """
            )

            st.slider(
                "Daily study goal (minutes)",
                min_value=15,
                max_value=120,
                step=5,
                key="study_goal",
            )

            st.slider(
                "Target score",
                min_value=400,
                max_value=1600,
                step=10,
                key="target_score",
            )

            st.selectbox(
                "Default subject",
                [
                    "SATSam recommendation",
                    "Math",
                    "Reading and Writing",
                    "Balanced",
                ],
                key="default_practice_subject",
            )

            st.select_slider(
                "Default starting difficulty",
                options=["Foundation", "Standard", "Challenging", "Test-level"],
                key="default_start_difficulty",
            )

            st.slider(
                "Default number of questions",
                min_value=5,
                max_value=30,
                step=1,
                key="default_practice_count",
            )

            st.toggle("Explain answers automatically", key="auto_explain")
            st.toggle("Show suggested timing during practice", key="show_timing")

    with ai_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Sam, your AI tutor</div>
                <div class="card-subtitle">
                    Runs on a local Ollama model — nothing leaves your machine
                </div>
                """
            )

            st.toggle("Enable Sam (AI features)", key="ai_enabled")
            st.text_input("Ollama host", key="ai_host")
            st.text_input("Model", key="ai_model")
            st.slider(
                "Response creativity",
                min_value=0.0,
                max_value=1.0,
                step=0.1,
                key="ai_temperature",
            )

            st.selectbox(
                "Explanation style",
                list(COACH_STYLE_GUIDANCE.keys()),
                key="explanation_style",
            )
            st.selectbox(
                "Coach personality",
                list(COACH_PERSONALITY_GUIDANCE.keys()),
                key="coach_personality",
            )

            if st.button("Test connection", use_container_width=True):
                with st.spinner("Reaching your local model…"):
                    ok, info = ollama_reachable(
                        st.session_state.ai_host or "http://localhost:11434"
                    )
                if ok:
                    models = ", ".join(info) if info else "no models found"
                    st.success(f"Connected. Available models: {models}")
                    if st.session_state.ai_model not in info and info:
                        st.caption(
                            f"Heads up: '{st.session_state.ai_model}' isn't in that "
                            "list. Pull it with your Ollama tool, or switch to one "
                            "above."
                        )
                else:
                    st.error(
                        "Couldn't reach Ollama. Make sure it's running, then try "
                        f"again. ({info})"
                    )

    # Data section.
    section_header(
        "Your data",
        "It stays with you",
        "Export a copy or start fresh whenever you like.",
    )

    with st.container(border=True):
        data_col_1, data_col_2, data_col_3 = st.columns(3)

        with data_col_1:
            export_payload = json.dumps(
                {
                    "history": st.session_state.history,
                    "score_history": st.session_state.score_history,
                    "sessions_completed": st.session_state.sessions_completed,
                },
                default=str,
                indent=2,
            )
            st.download_button(
                "Export progress",
                data=export_payload,
                file_name="satsam-progress.json",
                mime="application/json",
                use_container_width=True,
            )

        with data_col_2:
            if st.button("Reset progress", use_container_width=True):
                st.session_state.history = []
                st.session_state.score_history = []
                st.session_state.sessions_completed = 0
                st.session_state.best_streak = 0
                st.session_state.ai_explanations = {}
                st.session_state.error_fingerprint_cache = {}
                st.session_state.ai_review_cache = {}
                st.success("Progress cleared. Fresh start whenever you're ready.")
                st.rerun()

        with data_col_3:
            if st.button(
                "Save preferences",
                type="primary",
                use_container_width=True,
            ):
                try:
                    save_settings()
                    st.success("Preferences saved.")
                except Exception as error:
                    st.error(f"Couldn't save: {error}")
