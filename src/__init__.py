"""SATSam — a warm, adaptive, locally-powered SAT coach.

Package layout:
- ``config``        constants and session-state defaults
- ``paths``         filesystem locations
- ``html_utils``    raw-HTML rendering helpers for Streamlit
- ``data_loader``   the question bank
- ``settings_store``preference persistence
- ``metrics``       stats derived from answer history
- ``helpers``       small presentation helpers
- ``questions``     adaptive selection and answer checking
- ``state``         session-state setup and the practice lifecycle
- ``styles``        the global stylesheet
- ``ai``            Sam, the local-model tutor
- ``components``    shared UI (cards, timer, chat, sidebar)
- ``views``         one module per page
"""
