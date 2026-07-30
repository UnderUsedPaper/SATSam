"""Preference persistence.

Preferences are saved to ``satsam-settings.json`` at the project root so they
survive an app restart. Progress (answer history) intentionally stays in the
session only.
"""

import json
from datetime import date

import streamlit as st

from src.config import PERSISTED_KEYS
from src.paths import SETTINGS_FILE


def settings_path():
    return SETTINGS_FILE


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
