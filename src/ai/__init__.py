"""Sam, the local-model AI tutor.

Submodules:
- ``client``       transport to the local Ollama server + JSON parsing
- ``prompts``      system prompts and question formatting
- ``explanations`` per-answer coaching explanations
- ``fingerprint``  the AI Error Fingerprint (diagnosis + fallback + card)
- ``coaching``     focus-skill targeting and end-of-session review
- ``study_plan``   the validated seven-day study plan
"""
