"""Filesystem paths, resolved relative to the project root.

`src/paths.py` lives one level below the repository root, so the root is the
parent of this file's directory. Everything else is derived from there, which
keeps the app working no matter where the repo is cloned.
"""

import os

# Repository root (the folder that contains app.py and this src/ package).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")

# The question bank ships in data/. The loader also falls back to a couple of
# legacy locations so an older checkout keeps working.
QUESTIONS_FILE = os.path.join(DATA_DIR, "sat-questions.json")

# User-generated files. These are written at runtime and are git-ignored.
SETTINGS_FILE = os.path.join(BASE_DIR, "satsam-settings.json")
