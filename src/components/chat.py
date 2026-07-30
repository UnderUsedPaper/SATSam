"""Chat with Sam — a free-form dialog plus the floating launcher.

The dialog can be opened blank from the sidebar/launcher, or pre-grounded in a
specific missed question via ``open_question_chat``.
"""

import streamlit as st

from src.ai.client import ollama_chat_multi
from src.html_utils import esc, render_html


def open_question_chat(question, user_answer):
    """Open the chat pre-grounded in a specific missed question."""
    skill = question.get("skill", "this one")
    st.session_state.chat_context = {
        "question": question,
        "user_answer": str(user_answer),
    }
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": (
                f"No worries at all — {skill} trips up plenty of people. "
                "Tell me which part felt confusing, or just say \"walk me through "
                "it\" and we'll take it one step at a time together."
            ),
        }
    ]
    st.session_state.chat_pending = None
    st.session_state.chat_open = True


@st.dialog("Chat with Sam ✦", width="large")
def render_chat_dialog():
    render_html(
        '<div style="color: var(--muted); font-size: 0.85rem; '
        'margin: -0.25rem 0 0.9rem 0;">Ask me anything — a concept you\'re stuck '
        'on, how to plan your week, or a question you just missed. I\'m glad '
        'you\'re here.</div>'
    )

    if st.session_state.get("chat_context"):
        skill = st.session_state.chat_context.get("question", {}).get("skill", "")
        if skill:
            render_html(
                f'<div style="display:inline-block; margin-bottom:0.9rem; '
                f'padding:5px 11px; border-radius:999px; background:var(--sage-soft); '
                f'color:#536853; font-size:0.7rem; font-weight:700;">'
                f'Talking through: {esc(skill)}</div>'
            )

    # Conversation so far.
    for message in st.session_state.get("chat_messages", []):
        role = "user" if message["role"] == "user" else "assistant"
        avatar = "🧑" if role == "user" else "✨"
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])

    # Answer a pending message now, so the spinner shows inside the dialog.
    pending = st.session_state.get("chat_pending")
    if pending:
        st.session_state.chat_pending = None
        if st.session_state.get("ai_enabled"):
            with st.chat_message("assistant", avatar="✨"):
                with st.spinner("Sam is thinking…"):
                    ok, reply = ollama_chat_multi(st.session_state.chat_messages)
                if not ok or not reply:
                    reply = (
                        "I'm having trouble reaching your local AI model right now. "
                        "Make sure Ollama is running, then try again — I'll be right "
                        "here when you're ready."
                    )
                st.markdown(reply)
        else:
            reply = (
                "The AI tutor is switched off at the moment. Flip it on in Settings "
                "once your local Ollama model is running, and I'll be able to chat "
                "with you here."
            )
            with st.chat_message("assistant", avatar="✨"):
                st.markdown(reply)
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": reply}
        )

    # Input.
    with st.form("chat_form", clear_on_submit=True):
        user_text = st.text_area(
            "Your message",
            placeholder="Message Sam…",
            height=80,
            label_visibility="collapsed",
            key="chat_input_text",
        )
        sent = st.form_submit_button(
            "Send", type="primary", use_container_width=True
        )
    if sent and user_text and user_text.strip():
        st.session_state.chat_messages.append(
            {"role": "user", "content": user_text.strip()}
        )
        st.session_state.chat_pending = user_text.strip()
        st.rerun(scope="fragment")

    st.write("")
    close_col_a, close_col_b = st.columns(2)
    with close_col_a:
        if st.button("Clear chat", use_container_width=True, key="chat_clear"):
            st.session_state.chat_messages = []
            st.session_state.chat_context = None
            st.session_state.chat_pending = None
            st.rerun(scope="fragment")
    with close_col_b:
        if st.button("Close", type="primary", use_container_width=True,
                     key="chat_close"):
            st.session_state.chat_open = False
            st.rerun()


def render_floating_chat():
    """The floating launcher button and the dialog trigger, on every page."""
    if st.button("💬", key="floating_chat_btn", help="Chat with Sam"):
        st.session_state.chat_open = True

    if st.session_state.get("chat_open"):
        # Consume the "open" intent right away. Streamlit keeps the dialog open on
        # its own after this call; interactions inside it rerun only the dialog
        # (fragment scope). This way a full-script rerun from navigating tabs or
        # dismissing the dialog won't re-open it.
        st.session_state.chat_open = False
        render_chat_dialog()
