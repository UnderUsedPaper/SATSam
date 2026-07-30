"""Helpers for injecting raw HTML into Streamlit.

Streamlit renders Markdown first and HTML second. Any line that starts with
four or more spaces becomes a fenced code block, and a blank line ends a raw
HTML block. Flattening every markup string to a single line removes both
triggers, which is why every template passes through ``flatten_html`` before
it reaches ``st.markdown``.
"""

import html as html_lib

import streamlit as st


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
