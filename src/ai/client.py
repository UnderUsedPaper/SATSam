"""Local model transport (Ollama).

All generation flows through ``ollama_chat`` / ``ollama_chat_multi``, which talk
to the local Ollama server configured in Settings. Every feature that uses the
model degrades gracefully: if the server is unreachable or returns something
unexpected, callers fall back to built-in explanations and heuristics.
"""

import json
import re
import urllib.request

import ollama
import streamlit as st

from src.ai.prompts import build_chat_system_prompt

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


def ollama_chat_multi(messages, temperature=None):
    """Send a full multi-turn conversation to the local model. `messages` is a list
    of {"role", "content"} dicts (user/assistant), without the system message.
    Returns (True, text) on success or (False, error_message)."""
    if temperature is None:
        temperature = st.session_state.get("ai_temperature", 0.7)

    kwargs = {
        "model": st.session_state.get("ai_model", "qwen3:8b"),
        "messages": (
            [{"role": "system", "content": build_chat_system_prompt()}]
            + list(messages)
        ),
        "options": {"temperature": float(temperature)},
    }

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
