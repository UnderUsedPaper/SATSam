"""The global stylesheet.

Class names are kept stable so the view code doesn't need to change. This pass
focuses on contrast, hierarchy, and depth so the app reads as an intentional
product rather than raw Streamlit:

- Deeper, saturated terracotta on "banner" boxes (hero kicker, practice header)
  with cream/white text for high contrast and legibility.
- A darker, warmer body-text color everywhere so nothing looks washed out.
- Noticeably larger, higher-contrast type in the AI Study Plan day cards.
- More refined native widgets (inputs, sliders, radios) and layered shadows.
"""

from src.html_utils import render_html


STYLES = """
<style>

@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Newsreader:opsz,wght@6..72,500;6..72,600;6..72,700&display=swap');

:root {
    --cream: #F6EFE2;
    --paper: #FFFDF8;
    --paper-muted: #F1EADD;
    --ink: #241F19;
    --espresso: #3A2C21;          /* deep body text on warm cards */
    --muted: #5F574C;             /* darker than before for crisp contrast */
    --muted-soft: #857B6D;

    --terracotta: #C4623F;
    --terracotta-dark: #9E4830;
    --terracotta-deep: #8A3D28;   /* banner backgrounds */
    --terracotta-soft: #F0D6C8;

    --sage: #63795F;
    --sage-dark: #46583F;
    --sage-soft: #DBE5D6;

    --brass: #C79640;
    --brass-dark: #8A6522;
    --brass-soft: #F2E4BD;

    --blue-soft: #DBE7EA;
    --border: #E3D9CB;
    --border-strong: #D7C9B6;

    --shadow: 0 18px 44px rgba(58, 42, 28, 0.10), 0 3px 10px rgba(58, 42, 28, 0.05);
    --shadow-small: 0 6px 18px rgba(58, 42, 28, 0.07);
    --radius: 20px;
}

html, body, [class*="css"] {
    font-family: "DM Sans", sans-serif;
    color: var(--ink);
    -webkit-font-smoothing: antialiased;
}
.stApp {
    background:
        radial-gradient(circle at 86% 2%, rgba(199, 150, 64, 0.11), transparent 26rem),
        radial-gradient(circle at 6% 96%, rgba(99, 121, 95, 0.10), transparent 30rem),
        var(--cream);
}
.block-container {
    max-width: 1340px;
    padding-top: 2.4rem;
    padding-bottom: 5rem;
    padding-left: 3rem;
    padding-right: 3rem;
}
h1, h2, h3 { color: var(--ink); letter-spacing: -0.01em; }
p { color: var(--muted); }
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
#MainMenu,
footer { visibility: hidden; }

.stApp pre, .stApp code {
    background: var(--paper-muted);
    color: var(--ink);
}

/* ----- SIDEBAR ----- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F0E7DA 0%, #ECE2D3 100%);
    border-right: 1px solid var(--border-strong);
}
section[data-testid="stSidebar"] > div { padding-top: 1.25rem; }
.sidebar-brand { padding: 0.4rem 0.35rem 1.2rem 0.35rem; }
.sidebar-brand-row { display: flex; align-items: center; gap: 0.75rem; }
.brand-mark {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(140deg, var(--terracotta), var(--terracotta-deep));
    color: #FFF7F0;
    font-family: "Newsreader", serif;
    font-weight: 700;
    font-size: 1.4rem;
    box-shadow: 0 8px 18px rgba(138, 61, 40, 0.28);
}
.brand-name {
    font-family: "Newsreader", serif;
    font-size: 1.7rem;
    font-weight: 600;
    line-height: 1;
    color: var(--ink);
}
.brand-caption { color: var(--muted); font-size: 0.75rem; margin-top: 0.18rem; }
.sidebar-label {
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.13em;
    font-size: 0.66rem;
    font-weight: 800;
    margin: 1.15rem 0 0.5rem 0.25rem;
}
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 0.3rem; }
section[data-testid="stSidebar"] label[data-baseweb="radio"] {
    background: transparent;
    padding: 0.72rem 0.85rem;
    border-radius: 12px;
    transition: all 0.18s ease;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] p {
    font-weight: 600;
    color: var(--muted);
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
    background: rgba(255, 255, 255, 0.55);
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
    background: var(--paper);
    box-shadow: var(--shadow-small);
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p {
    color: var(--terracotta-dark);
    font-weight: 700;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {
    display: none;
}
.sidebar-card {
    background: rgba(255, 253, 248, 0.78);
    border: 1px solid var(--border);
    padding: 1.05rem;
    border-radius: 16px;
    margin-top: 1rem;
}
.sidebar-card-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 800;
    color: var(--muted);
}
.sidebar-card-value {
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--ink);
    margin-top: 0.35rem;
}
.sidebar-card-detail { font-size: 0.76rem; color: var(--muted); margin-top: 0.22rem; }
.mini-progress {
    height: 7px;
    width: 100%;
    border-radius: 999px;
    background: #E2D7C8;
    overflow: hidden;
    margin-top: 0.8rem;
}
.mini-progress-fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--terracotta), var(--brass)); }

/* ----- HERO ----- */
.hero {
    position: relative;
    overflow: hidden;
    min-height: 244px;
    padding: 2.7rem 2.8rem;
    margin-bottom: 2rem;
    border-radius: 28px;
    background: linear-gradient(125deg, #FFFDF8 0%, #F3DDCC 100%);
    border: 1px solid var(--border-strong);
    box-shadow: var(--shadow);
}
.hero::after {
    content: "";
    position: absolute;
    right: -70px;
    top: -100px;
    width: 360px;
    height: 360px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(196, 98, 63, 0.22) 0%, rgba(199, 150, 64, 0.12) 44%, transparent 70%);
}
.hero::before {
    content: "✦";
    position: absolute;
    right: 132px;
    top: 52px;
    font-size: 5rem;
    color: rgba(138, 61, 40, 0.12);
    transform: rotate(12deg);
    z-index: 1;
}
.hero-content { position: relative; z-index: 2; max-width: 760px; }
.hero-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.5rem 0.85rem;
    border-radius: 999px;
    background: var(--terracotta-deep);
    border: 1px solid var(--terracotta-deep);
    color: #FCEFE7;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    margin-bottom: 1.1rem;
    box-shadow: 0 6px 14px rgba(138, 61, 40, 0.22);
}
.hero h1 {
    font-family: "Newsreader", serif;
    font-size: clamp(2.6rem, 5vw, 4.1rem);
    line-height: 1;
    letter-spacing: -0.03em;
    margin: 0;
    max-width: 760px;
    color: var(--ink);
}
.hero h1 span { color: var(--terracotta-dark); }
.hero p {
    max-width: 610px;
    font-size: 1.02rem;
    line-height: 1.65;
    margin: 1.1rem 0 0 0;
    color: var(--espresso);
}
.hero-chips { display: flex; flex-wrap: wrap; gap: 0.65rem; margin-top: 1.55rem; }
.hero-chip {
    background: rgba(255, 253, 248, 0.85);
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    padding: 0.5rem 0.9rem;
    color: var(--espresso);
    font-size: 0.78rem;
    font-weight: 600;
}

/* ----- METRIC CARDS ----- */
.metric-card {
    min-height: 158px;
    background: var(--paper);
    border: 1px solid var(--border);
    border-radius: 19px;
    padding: 1.35rem;
    box-shadow: var(--shadow-small);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.metric-card:hover { transform: translateY(-3px); box-shadow: var(--shadow); }
.metric-top { display: flex; align-items: center; gap: 0.55rem; }
.metric-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: var(--terracotta-soft);
    color: var(--terracotta-dark);
    font-size: 0.95rem;
    font-weight: 700;
}
.metric-label { color: var(--muted); font-size: 0.77rem; font-weight: 700; letter-spacing: 0.01em; }
.metric-value {
    font-family: "Newsreader", serif;
    font-size: 2.3rem;
    font-weight: 600;
    color: var(--ink);
    line-height: 1;
    margin-top: 1rem;
}
.metric-detail { color: var(--muted); font-size: 0.74rem; margin-top: 0.55rem; }

/* ----- GENERAL CARDS AND HEADINGS ----- */
.section-heading { margin: 3rem 0 1.2rem 0; }
.section-heading .eyebrow {
    color: var(--terracotta-dark);
    text-transform: uppercase;
    letter-spacing: 0.13em;
    font-size: 0.68rem;
    font-weight: 800;
    margin-bottom: 0.4rem;
}
.section-heading h2 {
    font-family: "Newsreader", serif;
    font-size: 2.05rem;
    letter-spacing: -0.02em;
    margin: 0;
}
.section-heading p { margin: 0.42rem 0 0 0; font-size: 0.9rem; color: var(--muted); }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--paper);
    border: 1px solid var(--border);
    border-radius: 21px;
    box-shadow: var(--shadow-small);
}
div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 1.5rem; }
.card-title {
    font-family: "Newsreader", serif;
    color: var(--ink);
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}
.card-subtitle { color: var(--muted); font-size: 0.82rem; margin-bottom: 1rem; line-height: 1.5; }

/* ----- DAILY PLAN (home session outline) ----- */
.plan-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.95rem 0;
    border-bottom: 1px solid var(--border);
}
.plan-item:last-child { border-bottom: none; }
.plan-left { display: flex; align-items: center; gap: 0.85rem; }
.plan-number {
    width: 36px;
    height: 36px;
    min-width: 36px;
    border-radius: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--terracotta-soft);
    color: var(--terracotta-dark);
    font-weight: 800;
    font-size: 0.76rem;
}
.plan-name { color: var(--ink); font-size: 0.9rem; font-weight: 700; }
.plan-description { color: var(--muted); font-size: 0.75rem; margin-top: 0.15rem; }
.plan-time { color: var(--espresso); font-size: 0.74rem; font-weight: 700; white-space: nowrap; }

/* ----- AI INSIGHT ----- */
.ai-insight {
    position: relative;
    overflow: hidden;
    padding: 1.4rem;
    border-radius: 18px;
    background: linear-gradient(135deg, var(--sage-soft), #EBF0E6);
    border: 1px solid #CBD8C5;
    margin-bottom: 1rem;
}
.ai-insight-label {
    color: var(--sage-dark);
    text-transform: uppercase;
    letter-spacing: 0.11em;
    font-size: 0.66rem;
    font-weight: 800;
}
.ai-insight h3 { font-family: "Newsreader", serif; font-size: 1.5rem; margin: 0.4rem 0; color: var(--ink); }
.ai-insight p { color: #4C5648; font-size: 0.84rem; line-height: 1.62; margin: 0; }
.coach-quote {
    padding: 1.15rem 1.2rem;
    border-left: 4px solid var(--brass);
    border-radius: 0 14px 14px 0;
    background: var(--brass-soft);
    color: #6A521F;
    font-family: "Newsreader", serif;
    font-size: 1.08rem;
    line-height: 1.5;
}

/* ----- PROGRESS RING ----- */
.progress-ring-card { text-align: center; padding: 0.5rem 0 0.2rem 0; }
.progress-ring {
    --progress: 62%;
    width: 146px;
    height: 146px;
    margin: 0.4rem auto 1rem auto;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: conic-gradient(var(--terracotta) var(--progress), #E7DCCD 0);
    position: relative;
}
.progress-ring::after {
    content: "";
    position: absolute;
    width: 114px;
    height: 114px;
    border-radius: 50%;
    background: var(--paper);
}
.progress-ring-content { position: relative; z-index: 2; }
.progress-ring-value {
    font-family: "Newsreader", serif;
    font-weight: 600;
    font-size: 1.8rem;
    color: var(--ink);
}
.progress-ring-label { color: var(--muted); font-size: 0.7rem; }

/* ----- TOPIC ANALYTICS ----- */
.topic-row { padding: 1rem 0; border-bottom: 1px solid var(--border); }
.topic-row:last-child { border-bottom: none; }
.topic-row-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.65rem;
}
.topic-name { color: var(--ink); font-weight: 700; font-size: 0.88rem; }
.topic-score {
    color: var(--ink);
    font-family: "Newsreader", serif;
    font-size: 1.18rem;
    font-weight: 600;
}
.topic-status {
    display: inline-block;
    margin-top: 0.24rem;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.02em;
}
.needs-work { color: var(--terracotta-dark); }
.developing { color: var(--brass-dark); }
.strong { color: var(--sage-dark); }
.topic-progress-track {
    width: 100%;
    height: 8px;
    background: #E9DFD2;
    overflow: hidden;
    border-radius: 999px;
}
.topic-progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--terracotta), var(--brass));
}

/* ----- ACTIVITY ----- */
.activity-item {
    display: flex;
    gap: 0.8rem;
    padding: 0.85rem 0;
    border-bottom: 1px solid var(--border);
}
.activity-item:last-child { border-bottom: none; }
.activity-dot {
    width: 10px;
    height: 10px;
    min-width: 10px;
    border-radius: 50%;
    background: var(--sage);
    margin-top: 0.32rem;
    box-shadow: 0 0 0 4px var(--sage-soft);
}
.activity-dot.miss { background: var(--terracotta); box-shadow: 0 0 0 4px var(--terracotta-soft); }
.activity-title { color: var(--ink); font-size: 0.82rem; font-weight: 700; }
.activity-detail { color: var(--muted); font-size: 0.71rem; margin-top: 0.15rem; }

/* ----- PRACTICE QUESTION ----- */
/* Deep terracotta banner with high-contrast cream text. */
.practice-header {
    padding: 1.5rem 1.6rem;
    border-radius: 20px;
    background: linear-gradient(130deg, var(--terracotta) 0%, var(--terracotta-deep) 100%);
    border: 1px solid var(--terracotta-deep);
    margin-bottom: 1.5rem;
    box-shadow: 0 12px 30px rgba(138, 61, 40, 0.22);
}
.practice-header-label {
    color: #F6D9CB;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.68rem;
    font-weight: 800;
}
.practice-header h2 {
    font-family: "Newsreader", serif;
    font-size: 1.9rem;
    margin: 0.35rem 0 0.3rem 0;
    color: #FFF8F2;
}
.practice-header p { color: rgba(255, 248, 242, 0.92); font-size: 0.92rem; margin: 0; line-height: 1.55; }
.question-number {
    color: var(--terracotta-dark);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.7rem;
    font-weight: 800;
}
.question-text {
    font-family: "Newsreader", serif;
    color: var(--ink);
    font-size: 1.5rem;
    line-height: 1.42;
    margin: 0.75rem 0 1.15rem 0;
}
.formula-box {
    padding: 1rem;
    text-align: center;
    background: var(--paper-muted);
    border: 1px solid var(--border);
    border-radius: 13px;
    color: var(--ink);
    font-family: Georgia, serif;
    font-size: 1.2rem;
    margin-bottom: 1rem;
}
.stimulus-box {
    padding: 1.1rem 1.2rem;
    background: var(--paper-muted);
    border: 1px solid var(--border);
    border-radius: 13px;
    color: var(--espresso);
    font-size: 0.98rem;
    line-height: 1.62;
    margin: 0.2rem 0 1.15rem 0;
}
.review-choice {
    padding: 0.7rem 0.95rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 0.5rem;
    font-size: 0.92rem;
    color: var(--ink);
    background: var(--paper);
}
.review-choice.correct {
    border-color: #8CAE8C;
    background: #E8F0E4;
    color: #37502F;
    font-weight: 700;
}
.review-choice.wrong {
    border-color: #D79A85;
    background: #F6E3DA;
    color: #8E4028;
}
.review-choice .tag { float: right; font-size: 0.72rem; font-weight: 800; letter-spacing: 0.04em; }

/* ----- STUDY PLAN DAYS ----- */
.day-card {
    padding: 1.2rem;
    border-radius: 16px;
    background: var(--paper);
    border: 1px solid var(--border);
    margin-bottom: 0.8rem;
}

/* The AI-generated detailed day card — noticeably larger, higher-contrast type
   so every field is comfortable to read at 100% zoom. */
.detailed-day-card {
    margin-bottom: 18px;
    padding: 22px 24px;
    border: 1px solid var(--border-strong);
    border-radius: 18px;
    background: var(--paper);
    box-shadow: var(--shadow-small);
}
.detailed-day-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
}
.detailed-day-card .day-name {
    margin-bottom: 8px;
    color: var(--terracotta-dark);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.13em;
    text-transform: uppercase;
}
.detailed-day-card .day-task {
    color: var(--ink);
    font-family: "Newsreader", Georgia, serif;
    font-size: 1.45rem;
    font-weight: 700;
    line-height: 1.25;
}
.plan-total-badge {
    flex: 0 0 auto;
    padding: 8px 13px;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    background: var(--terracotta-soft);
    color: var(--terracotta-dark);
    font-size: 0.8rem;
    font-weight: 800;
    white-space: nowrap;
}
.plan-focus-label {
    display: inline-block;
    margin-top: 13px;
    padding: 7px 13px;
    border-radius: 999px;
    background: var(--sage-soft);
    color: var(--sage-dark);
    font-size: 0.8rem;
    font-weight: 700;
}
.plan-rationale {
    margin-top: 14px;
    color: var(--espresso);
    font-size: 0.98rem;
    line-height: 1.62;
}
.plan-block-list {
    display: flex;
    flex-direction: column;
    gap: 11px;
    margin-top: 18px;
}
.plan-block {
    display: grid;
    grid-template-columns: 62px minmax(0, 1fr);
    gap: 14px;
    padding: 15px;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: #FBF6EE;
}
.plan-block-time {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 52px;
    border-radius: 12px;
    background: var(--terracotta-soft);
    color: var(--terracotta-dark);
    font-size: 0.92rem;
    font-weight: 850;
    line-height: 1.1;
    text-align: center;
}
.plan-block-content { min-width: 0; }
.plan-block-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}
.plan-block-title {
    color: var(--ink);
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.35;
}
.plan-block-questions {
    flex: 0 0 auto;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--sage-soft);
    color: var(--sage-dark);
    font-size: 0.7rem;
    font-weight: 800;
    white-space: nowrap;
}
.plan-block-description {
    margin-top: 6px;
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.6;
}
.plan-day-footer {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 0.82rem;
    line-height: 1.5;
}
@media (max-width: 900px) {
    .detailed-day-top { flex-direction: column; }
    .plan-block { grid-template-columns: 54px minmax(0, 1fr); }
    .plan-block-header { align-items: flex-start; flex-direction: column; }
}
.day-name {
    color: var(--terracotta-dark);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 800;
}
.day-task { color: var(--ink); font-weight: 700; font-size: 0.95rem; margin-top: 0.38rem; }
.day-detail { color: var(--muted); font-size: 0.76rem; margin-top: 0.28rem; }

/* ----- BUTTONS ----- */
.stButton > button {
    min-height: 46px;
    border: 1px solid var(--border-strong);
    border-radius: 13px;
    background: var(--paper);
    color: var(--ink);
    font-weight: 700;
    font-size: 0.84rem;
    box-shadow: none;
    transition: all 0.18s ease;
}
.stButton > button:hover {
    color: var(--terracotta-dark);
    border-color: var(--terracotta);
    background: #FFF8F2;
    transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    color: #FFF7F0;
    background: linear-gradient(135deg, var(--terracotta), var(--terracotta-dark));
    border-color: var(--terracotta-dark);
    box-shadow: 0 8px 18px rgba(138, 61, 40, 0.22);
}
.stButton > button[kind="primary"]:hover {
    color: #FFF7F0;
    background: linear-gradient(135deg, var(--terracotta-dark), var(--terracotta-deep));
    border-color: var(--terracotta-deep);
    transform: translateY(-1px);
}

/* ----- INPUTS ----- */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stDateInput"] input {
    background: var(--paper);
    border-color: var(--border-strong);
    border-radius: 12px;
    color: var(--ink);
}
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"] > div:focus-within {
    border-color: var(--terracotta);
}
.stTextArea textarea::placeholder,
.stTextInput input::placeholder { color: var(--muted-soft); }
div[data-baseweb="slider"] div[role="slider"] { background: var(--terracotta); }
div[data-baseweb="slider"] > div > div { background: var(--terracotta); }
div[data-testid="stProgress"] > div > div > div {
    background: linear-gradient(90deg, var(--terracotta), var(--brass));
}
label p { font-weight: 600; color: var(--espresso); }

/* ----- RADIO OPTIONS IN THE MAIN AREA ----- */
div[data-testid="stMain"] div[role="radiogroup"] { gap: 0.55rem; }
div[data-testid="stMain"] label[data-baseweb="radio"] {
    background: var(--paper);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.82rem 0.95rem;
    transition: all 0.16s ease;
}
div[data-testid="stMain"] label[data-baseweb="radio"]:hover { border-color: var(--border-strong); }
div[data-testid="stMain"] label[data-baseweb="radio"]:has(input:checked) {
    border-color: var(--terracotta);
    background: #FFF7F2;
    box-shadow: var(--shadow-small);
}

/* ----- CHAT WITH SAM ----- */
div[data-testid="stChatMessage"] { background: transparent; }

/* ----- STREAMLIT ALERTS ----- */
div[data-testid="stAlert"] { border-radius: 14px; border: 1px solid var(--border); }

/* ----- FLOATING CHAT LAUNCHER ----- */
.st-key-floating_chat_btn {
    position: fixed;
    right: 26px;
    bottom: 26px;
    z-index: 1000;
    width: auto;
}
.st-key-floating_chat_btn button {
    width: 62px;
    height: 62px;
    min-height: 62px;
    padding: 0;
    border-radius: 50% !important;
    font-size: 1.55rem;
    background: linear-gradient(140deg, var(--terracotta), var(--terracotta-deep)) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 14px 32px rgba(138, 61, 40, 0.42) !important;
}
.st-key-floating_chat_btn button:hover {
    transform: translateY(-3px) !important;
    color: #fff !important;
}

/* ----- RESPONSIVE ----- */
@media (max-width: 900px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .hero { padding: 1.8rem; }
    .hero::before { display: none; }
}

</style>
"""


def inject_global_styles():
    render_html(STYLES)
