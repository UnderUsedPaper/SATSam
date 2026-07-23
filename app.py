import streamlit as st
from datetime import date, datetime


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="SATSam — Your Personal SAT Coach",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# HTML HELPER
#
# Streamlit renders markdown first, HTML second. Any line that
# starts with four or more spaces becomes a fenced code block,
# and a blank line ends the raw-HTML block. That is what caused
# the stray <div> text and dark code boxes. Flattening every
# markup string to a single line removes both triggers.
# ============================================================

def flatten_html(markup: str) -> str:
    return " ".join(
        line.strip()
        for line in markup.splitlines()
        if line.strip()
    )


def render_html(markup: str) -> None:
    st.markdown(flatten_html(markup), unsafe_allow_html=True)


# ============================================================
# SESSION STATE
# ============================================================

PAGES = [
    "Home",
    "Practice",
    "Insights",
    "Study Plan",
    "Focus Timer",
    "Settings",
]

DEFAULT_STATE = {
    "questions_solved": 124,
    "correct_answers": 101,
    "study_minutes": 315,
    "predicted_score": 1410,
    "study_goal": 45,
    "today_minutes": 28,
    "streak": 5,
    "target_score": 1500,
    "sat_date": date(2026, 9, 6),
    "pomodoro_running": False,
    "practice_started": False,
    "answer_submitted": False,
    "page": "Home",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Navigation requested by a button on the previous run. This has to
# be applied *before* the sidebar radio is created, because Streamlit
# refuses to let a widget's key be modified after instantiation.
if "pending_page" in st.session_state:
    st.session_state.page = st.session_state.pop("pending_page")


def go_to(page_name: str) -> None:
    st.session_state.pending_page = page_name
    st.rerun()


# ============================================================
# HELPERS
# ============================================================

def days_until_sat() -> int:
    return max((st.session_state.sat_date - date.today()).days, 0)


def format_sat_date() -> str:
    # %-d / %#d are platform specific, so build the day number manually.
    d = st.session_state.sat_date
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def prep_window_percent(window_days: int = 180) -> int:
    elapsed = window_days - days_until_sat()
    return max(0, min(round(elapsed / window_days * 100), 100))


def accuracy() -> int:
    if st.session_state.questions_solved == 0:
        return 0

    return round(
        st.session_state.correct_answers
        / st.session_state.questions_solved
        * 100
    )


def greeting() -> str:
    hour = datetime.now().hour

    if hour < 12:
        return "Good morning"
    elif hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"


def metric_card(label, value, detail, icon):
    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-top">
                <span class="metric-icon">{icon}</span>
                <span class="metric-label">{label}</span>
            </div>
            <div class="metric-value">{value}</div>
            <div class="metric-detail">{detail}</div>
        </div>
        """
    )


def section_header(eyebrow, title, description=""):
    render_html(
        f"""
        <div class="section-heading">
            <div class="eyebrow">{eyebrow}</div>
            <h2>{title}</h2>
            <p>{description}</p>
        </div>
        """
    )


def topic_row(topic, accuracy_value, status):
    status_class = status.lower().replace(" ", "-")
    width = max(0, min(accuracy_value, 100))

    render_html(
        f"""
        <div class="topic-row">
            <div class="topic-row-top">
                <div>
                    <div class="topic-name">{topic}</div>
                    <div class="topic-status {status_class}">{status}</div>
                </div>
                <div class="topic-score">{accuracy_value}%</div>
            </div>
            <div class="topic-progress-track">
                <div class="topic-progress-fill" style="width: {width}%;"></div>
            </div>
        </div>
        """
    )


# ============================================================
# GLOBAL STYLING
# ============================================================

STYLES = """
<style>

/* ----- IMPORT FONT ----- */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap');

/* ----- ROOT DESIGN TOKENS ----- */
:root {
    --cream: #F8F3EA;
    --paper: #FFFDF8;
    --paper-muted: #F3EDE3;
    --ink: #28241F;
    --muted: #746D63;
    --terracotta: #C9694A;
    --terracotta-dark: #A95036;
    --terracotta-soft: #F2D8CB;
    --sage: #6F856F;
    --sage-soft: #DEE7DC;
    --mustard: #D9A441;
    --mustard-soft: #F5E7BC;
    --blue-soft: #DDE8EB;
    --border: #E6DDD1;
    --shadow: 0 14px 35px rgba(70, 53, 38, 0.08);
    --shadow-small: 0 5px 16px rgba(70, 53, 38, 0.06);
}

/* ----- APP FOUNDATION ----- */
html, body, [class*="css"] {
    font-family: "DM Sans", sans-serif;
    color: var(--ink);
}
.stApp {
    background:
        radial-gradient(circle at 84% 4%, rgba(217, 164, 65, 0.13), transparent 24rem),
        radial-gradient(circle at 10% 95%, rgba(111, 133, 111, 0.12), transparent 28rem),
        var(--cream);
}
.block-container {
    max-width: 1380px;
    padding-top: 2rem;
    padding-bottom: 4rem;
    padding-left: 2.7rem;
    padding-right: 2.7rem;
}
h1, h2, h3 { color: var(--ink); }
p { color: var(--muted); }
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
#MainMenu,
footer { visibility: hidden; }

/* Any HTML that still slips through markdown should not become a dark block. */
.stApp pre, .stApp code {
    background: var(--paper-muted);
    color: var(--ink);
}

/* ----- SIDEBAR ----- */
section[data-testid="stSidebar"] {
    background: #F1E9DE;
    border-right: 1px solid #E0D5C7;
}
section[data-testid="stSidebar"] > div { padding-top: 1.25rem; }
.sidebar-brand { padding: 0.4rem 0.35rem 1.2rem 0.35rem; }
.sidebar-brand-row { display: flex; align-items: center; gap: 0.75rem; }
.brand-mark {
    width: 42px;
    height: 42px;
    border-radius: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--terracotta);
    color: white;
    font-size: 1.25rem;
    box-shadow: 0 7px 16px rgba(169, 80, 54, 0.21);
}
.brand-name {
    font-family: "Newsreader", serif;
    font-size: 1.65rem;
    font-weight: 600;
    line-height: 1;
    color: var(--ink);
}
.brand-caption { color: var(--muted); font-size: 0.74rem; margin-top: 0.16rem; }
.sidebar-label {
    color: #877E72;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.65rem;
    font-weight: 700;
    margin: 0.8rem 0 0.5rem 0.25rem;
}
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 0.25rem; }
section[data-testid="stSidebar"] label[data-baseweb="radio"] {
    background: transparent;
    padding: 0.72rem 0.8rem;
    border-radius: 11px;
    transition: all 0.18s ease;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
    background: rgba(255, 255, 255, 0.48);
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
    background: rgba(255, 253, 248, 0.7);
    border: 1px solid rgba(222, 210, 195, 0.9);
    padding: 1rem;
    border-radius: 15px;
    margin-top: 1rem;
}
.sidebar-card-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-weight: 700;
    color: #8B8175;
}
.sidebar-card-value {
    font-size: 1rem;
    font-weight: 700;
    color: var(--ink);
    margin-top: 0.35rem;
}
.sidebar-card-detail { font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }
.mini-progress {
    height: 7px;
    width: 100%;
    border-radius: 999px;
    background: #E4DACE;
    overflow: hidden;
    margin-top: 0.8rem;
}
.mini-progress-fill { height: 100%; border-radius: inherit; background: var(--terracotta); }

/* ----- HERO ----- */
.hero {
    position: relative;
    overflow: hidden;
    min-height: 252px;
    padding: 2.5rem 2.65rem;
    margin-bottom: 1.65rem;
    border-radius: 26px;
    background: linear-gradient(125deg, rgba(255, 253, 248, 0.98), rgba(244, 226, 210, 0.95));
    border: 1px solid rgba(215, 193, 173, 0.8);
    box-shadow: var(--shadow);
}
.hero::after {
    content: "";
    position: absolute;
    right: -70px;
    top: -100px;
    width: 380px;
    height: 380px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(201, 105, 74, 0.25) 0%, rgba(217, 164, 65, 0.12) 44%, transparent 70%);
}
.hero::before {
    content: "✦";
    position: absolute;
    right: 128px;
    top: 46px;
    font-size: 5.8rem;
    color: rgba(169, 80, 54, 0.16);
    transform: rotate(12deg);
    z-index: 1;
}
.hero-content { position: relative; z-index: 2; max-width: 760px; }
.hero-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.46rem 0.78rem;
    border-radius: 999px;
    background: rgba(255, 253, 248, 0.72);
    border: 1px solid rgba(201, 105, 74, 0.18);
    color: var(--terracotta-dark);
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.035em;
    margin-bottom: 1rem;
}
.hero h1 {
    font-family: "Newsreader", serif;
    font-size: clamp(2.7rem, 5vw, 4.35rem);
    line-height: 0.98;
    letter-spacing: -0.045em;
    margin: 0;
    max-width: 760px;
}
.hero h1 span { color: var(--terracotta); }
.hero p {
    max-width: 610px;
    font-size: 1rem;
    line-height: 1.65;
    margin: 1rem 0 0 0;
    color: #6F665B;
}
.hero-chips { display: flex; flex-wrap: wrap; gap: 0.65rem; margin-top: 1.35rem; }
.hero-chip {
    background: rgba(255, 253, 248, 0.7);
    border: 1px solid rgba(193, 169, 149, 0.5);
    border-radius: 999px;
    padding: 0.48rem 0.75rem;
    color: #655D53;
    font-size: 0.77rem;
    font-weight: 600;
}

/* ----- METRIC CARDS ----- */
.metric-card {
    min-height: 158px;
    background: rgba(255, 253, 248, 0.91);
    border: 1px solid var(--border);
    border-radius: 19px;
    padding: 1.2rem;
    box-shadow: var(--shadow-small);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.metric-card:hover { transform: translateY(-3px); box-shadow: var(--shadow); }
.metric-top { display: flex; align-items: center; gap: 0.55rem; }
.metric-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 31px;
    height: 31px;
    border-radius: 10px;
    background: var(--paper-muted);
    color: var(--terracotta-dark);
    font-size: 0.92rem;
}
.metric-label { color: var(--muted); font-size: 0.75rem; font-weight: 600; }
.metric-value {
    font-family: "Newsreader", serif;
    font-size: 2.25rem;
    font-weight: 600;
    color: var(--ink);
    line-height: 1;
    margin-top: 1rem;
}
.metric-detail { color: #8A8176; font-size: 0.72rem; margin-top: 0.55rem; }

/* ----- GENERAL CARDS AND HEADINGS ----- */
.section-heading { margin: 2.25rem 0 1rem 0; }
.section-heading .eyebrow {
    color: var(--terracotta-dark);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.66rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
}
.section-heading h2 {
    font-family: "Newsreader", serif;
    font-size: 2rem;
    letter-spacing: -0.025em;
    margin: 0;
}
.section-heading p { margin: 0.38rem 0 0 0; font-size: 0.88rem; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(255, 253, 248, 0.92);
    border: 1px solid var(--border);
    border-radius: 21px;
    box-shadow: var(--shadow-small);
}
div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 1.3rem; }
.card-title {
    font-family: "Newsreader", serif;
    color: var(--ink);
    font-size: 1.45rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}
.card-subtitle { color: var(--muted); font-size: 0.8rem; margin-bottom: 1rem; }

/* ----- DAILY PLAN ----- */
.plan-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.95rem 0;
    border-bottom: 1px solid #EEE7DE;
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
    background: var(--paper-muted);
    color: var(--terracotta-dark);
    font-weight: 700;
    font-size: 0.75rem;
}
.plan-name { color: var(--ink); font-size: 0.88rem; font-weight: 700; }
.plan-description { color: var(--muted); font-size: 0.72rem; margin-top: 0.15rem; }
.plan-time { color: #766E63; font-size: 0.72rem; font-weight: 600; white-space: nowrap; }

/* ----- AI INSIGHT ----- */
.ai-insight {
    position: relative;
    overflow: hidden;
    padding: 1.25rem;
    border-radius: 17px;
    background: linear-gradient(135deg, var(--sage-soft), #EDF1E8);
    border: 1px solid #CFDBCB;
    margin-bottom: 1rem;
}
.ai-insight-label {
    color: #536853;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.65rem;
    font-weight: 800;
}
.ai-insight h3 { font-family: "Newsreader", serif; font-size: 1.45rem; margin: 0.4rem 0; }
.ai-insight p { color: #5C685B; font-size: 0.8rem; line-height: 1.55; margin: 0; }
.coach-quote {
    padding: 1.05rem 1.1rem;
    border-left: 3px solid var(--mustard);
    border-radius: 0 14px 14px 0;
    background: var(--mustard-soft);
    color: #705D34;
    font-family: "Newsreader", serif;
    font-size: 1.05rem;
    line-height: 1.45;
}

/* ----- PROGRESS RING ----- */
.progress-ring-card { text-align: center; padding: 0.5rem 0 0.2rem 0; }
.progress-ring {
    --progress: 62%;
    width: 142px;
    height: 142px;
    margin: 0.4rem auto 1rem auto;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: conic-gradient(var(--terracotta) var(--progress), #EAE1D6 0);
    position: relative;
}
.progress-ring::after {
    content: "";
    position: absolute;
    width: 111px;
    height: 111px;
    border-radius: 50%;
    background: var(--paper);
}
.progress-ring-content { position: relative; z-index: 2; }
.progress-ring-value {
    font-family: "Newsreader", serif;
    font-weight: 600;
    font-size: 1.75rem;
    color: var(--ink);
}
.progress-ring-label { color: var(--muted); font-size: 0.68rem; }

/* ----- TOPIC ANALYTICS ----- */
.topic-row { padding: 1rem 0; border-bottom: 1px solid #EEE6DC; }
.topic-row:last-child { border-bottom: none; }
.topic-row-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.65rem;
}
.topic-name { color: var(--ink); font-weight: 700; font-size: 0.85rem; }
.topic-score {
    color: var(--ink);
    font-family: "Newsreader", serif;
    font-size: 1.15rem;
    font-weight: 600;
}
.topic-status {
    display: inline-block;
    margin-top: 0.22rem;
    font-size: 0.65rem;
    font-weight: 700;
}
.needs-work { color: var(--terracotta-dark); }
.developing { color: #9A712A; }
.strong { color: #567056; }
.topic-progress-track {
    width: 100%;
    height: 7px;
    background: #ECE4DA;
    overflow: hidden;
    border-radius: 999px;
}
.topic-progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--terracotta), var(--mustard));
}

/* ----- ACTIVITY ----- */
.activity-item {
    display: flex;
    gap: 0.8rem;
    padding: 0.85rem 0;
    border-bottom: 1px solid #EEE7DE;
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
.activity-title { color: var(--ink); font-size: 0.8rem; font-weight: 700; }
.activity-detail { color: var(--muted); font-size: 0.69rem; margin-top: 0.15rem; }

/* ----- PRACTICE QUESTION ----- */
.practice-header {
    padding: 1.2rem 1.3rem;
    border-radius: 18px;
    background: linear-gradient(125deg, var(--terracotta-soft), #F6E8D7);
    border: 1px solid #E9CDBD;
    margin-bottom: 1.2rem;
}
.practice-header-label {
    color: var(--terracotta-dark);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.66rem;
    font-weight: 700;
}
.practice-header h2 { font-family: "Newsreader", serif; font-size: 1.8rem; margin: 0.3rem 0 0.2rem 0; }
.question-number {
    color: var(--terracotta-dark);
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-size: 0.68rem;
    font-weight: 700;
}
.question-text {
    font-family: "Newsreader", serif;
    color: var(--ink);
    font-size: 1.45rem;
    line-height: 1.4;
    margin: 0.7rem 0 1.1rem 0;
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

/* ----- STUDY PLAN DAYS ----- */
.day-card {
    padding: 1.1rem;
    border-radius: 16px;
    background: var(--paper);
    border: 1px solid var(--border);
    margin-bottom: 0.75rem;
}
.day-name {
    color: var(--terracotta-dark);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-weight: 800;
}
.day-task { color: var(--ink); font-weight: 700; font-size: 0.9rem; margin-top: 0.35rem; }
.day-detail { color: var(--muted); font-size: 0.72rem; margin-top: 0.25rem; }

/* ----- BUTTONS ----- */
.stButton > button {
    min-height: 44px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--paper);
    color: var(--ink);
    font-weight: 700;
    font-size: 0.82rem;
    box-shadow: none;
    transition: all 0.18s ease;
}
.stButton > button:hover {
    color: var(--terracotta-dark);
    border-color: #D9B09F;
    background: #FFF9F3;
    transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    color: white;
    background: var(--terracotta);
    border-color: var(--terracotta);
    box-shadow: 0 7px 17px rgba(169, 80, 54, 0.2);
}
.stButton > button[kind="primary"]:hover {
    color: white;
    background: var(--terracotta-dark);
    border-color: var(--terracotta-dark);
}

/* ----- INPUTS ----- */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stDateInput"] input {
    background: var(--paper);
    border-color: var(--border);
    border-radius: 11px;
}
div[data-baseweb="slider"] div[role="slider"] { background: var(--terracotta); }
div[data-baseweb="slider"] > div > div { background: var(--terracotta); }
div[data-testid="stProgress"] > div > div > div { background: var(--terracotta); }

/* ----- RADIO OPTIONS IN THE MAIN AREA ----- */
div[data-testid="stMain"] div[role="radiogroup"] { gap: 0.55rem; }
div[data-testid="stMain"] label[data-baseweb="radio"] {
    background: var(--paper);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.78rem 0.9rem;
}
div[data-testid="stMain"] label[data-baseweb="radio"]:has(input:checked) {
    border-color: var(--terracotta);
    background: #FFF7F2;
}

/* ----- STREAMLIT ALERTS ----- */
div[data-testid="stAlert"] { border-radius: 14px; border: 1px solid var(--border); }

/* ----- RESPONSIVE ----- */
@media (max-width: 900px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .hero { padding: 1.8rem; }
    .hero::before { display: none; }
}

</style>
"""

render_html(STYLES)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    render_html(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-row">
                <div class="brand-mark">S</div>
                <div>
                    <div class="brand-name">SATSam</div>
                    <div class="brand-caption">Thoughtful SAT preparation</div>
                </div>
            </div>
        </div>
        """
    )

    render_html('<div class="sidebar-label">Workspace</div>')

    page = st.radio(
        "Navigation",
        PAGES,
        key="page",
        label_visibility="collapsed",
    )

    render_html(
        f"""
        <div class="sidebar-card">
            <div class="sidebar-card-label">Next SAT</div>
            <div class="sidebar-card-value">
                {format_sat_date()}
            </div>
            <div class="sidebar-card-detail">{days_until_sat()} days remaining</div>
            <div class="mini-progress">
                <div class="mini-progress-fill" style="width: {prep_window_percent()}%;"></div>
            </div>
        </div>
        <div class="sidebar-card">
            <div class="sidebar-card-label">Current streak</div>
            <div class="sidebar-card-value">{st.session_state.streak} focused days</div>
            <div class="sidebar-card-detail">Your best streak is 12 days</div>
        </div>
        """
    )

    st.write("")

    if st.button(
        "Start quick practice",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.practice_started = True
        st.session_state.answer_submitted = False
        go_to("Practice")


# ============================================================
# HOME PAGE
# ============================================================

if page == "Home":
    goal = max(st.session_state.study_goal, 1)
    progress_fraction = min(st.session_state.today_minutes / goal, 1.0)
    progress_percent = round(progress_fraction * 100)

    render_html(
        f"""
        <div class="hero">
            <div class="hero-content">
                <div class="hero-kicker">✦ Your personalized plan is ready</div>
                <h1>{greeting()},<br>let's study with <span>purpose.</span></h1>
                <p>
                    SATSam turns every answer into a clearer picture of how you
                    think, then builds the next lesson around exactly what you need.
                </p>
                <div class="hero-chips">
                    <div class="hero-chip">{days_until_sat()} days until test day</div>
                    <div class="hero-chip">Target: {st.session_state.target_score}</div>
                    <div class="hero-chip">Focus: Linear equations</div>
                </div>
            </div>
        </div>
        """
    )

    metric_columns = st.columns(4)

    with metric_columns[0]:
        metric_card(
            "Predicted score",
            st.session_state.predicted_score,
            "+30 points this month",
            "↗",
        )

    with metric_columns[1]:
        metric_card(
            "Overall accuracy",
            f"{accuracy()}%",
            f"Across {st.session_state.questions_solved} questions",
            "✓",
        )

    with metric_columns[2]:
        metric_card(
            "Study time",
            f"{st.session_state.study_minutes // 60}h "
            f"{st.session_state.study_minutes % 60}m",
            "5 sessions this week",
            "◷",
        )

    with metric_columns[3]:
        metric_card(
            "Questions mastered",
            "18",
            "4 new topics improving",
            "◇",
        )

    section_header(
        "Today's path",
        "A focused session, built for you",
        "SATSam prioritizes the skills most likely to improve your score.",
    )

    main_left, main_right = st.columns([1.65, 1], gap="large")

    with main_left:
        with st.container(border=True):
            render_html(
                f"""
                <div class="card-title">Your {st.session_state.study_goal}-minute session</div>
                <div class="card-subtitle">
                    Balanced practice based on your latest performance
                </div>
                <div class="plan-item">
                    <div class="plan-left">
                        <div class="plan-number">01</div>
                        <div>
                            <div class="plan-name">Linear equations refresher</div>
                            <div class="plan-description">Review two concepts before practicing</div>
                        </div>
                    </div>
                    <div class="plan-time">8 min</div>
                </div>
                <div class="plan-item">
                    <div class="plan-left">
                        <div class="plan-number">02</div>
                        <div>
                            <div class="plan-name">Adaptive math set</div>
                            <div class="plan-description">Difficulty adjusts after every response</div>
                        </div>
                    </div>
                    <div class="plan-time">20 min</div>
                </div>
                <div class="plan-item">
                    <div class="plan-left">
                        <div class="plan-number">03</div>
                        <div>
                            <div class="plan-name">Reading inference drill</div>
                            <div class="plan-description">Practice evidence-based reasoning</div>
                        </div>
                    </div>
                    <div class="plan-time">12 min</div>
                </div>
                <div class="plan-item">
                    <div class="plan-left">
                        <div class="plan-number">04</div>
                        <div>
                            <div class="plan-name">Mistake reflection</div>
                            <div class="plan-description">Turn one error into a reusable strategy</div>
                        </div>
                    </div>
                    <div class="plan-time">5 min</div>
                </div>
                """
            )

            st.write("")

            if st.button(
                "Begin today's session →",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.practice_started = True
                st.session_state.answer_submitted = False
                go_to("Practice")

    with main_right:
        with st.container(border=True):
            render_html(
                f"""
                <div class="card-title">Daily progress</div>
                <div class="card-subtitle">Keep the session manageable and consistent</div>
                <div class="progress-ring-card">
                    <div class="progress-ring" style="--progress: {progress_percent}%;">
                        <div class="progress-ring-content">
                            <div class="progress-ring-value">{st.session_state.today_minutes}</div>
                            <div class="progress-ring-label">
                                of {st.session_state.study_goal} minutes
                            </div>
                        </div>
                    </div>
                </div>
                """
            )

            st.progress(progress_fraction)

            remaining = max(
                st.session_state.study_goal - st.session_state.today_minutes,
                0,
            )

            st.caption(f"{remaining} focused minutes remaining today")

        st.write("")

        render_html(
            """
            <div class="ai-insight">
                <div class="ai-insight-label">Sam's observation</div>
                <h3>You understand the method.</h3>
                <p>
                    Your recent algebra errors came from rushing the final
                    substitution—not from misunderstanding the concept. Today's
                    set will slow that specific step down.
                </p>
            </div>
            """
        )

        render_html(
            """
            <div class="coach-quote">
                &ldquo;Accuracy first. Speed follows familiarity.&rdquo;
            </div>
            """
        )

    section_header(
        "Performance snapshot",
        "Know what to strengthen next",
        "Each recommendation connects directly to your recent answers.",
    )

    topic_col, activity_col = st.columns([1.2, 1], gap="large")

    with topic_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Topic confidence</div>
                <div class="card-subtitle">
                    Estimated from accuracy, speed, and consistency
                </div>
                """
            )

            topic_row("Linear equations", 61, "Needs work")
            topic_row("Reading inference", 72, "Developing")
            topic_row("Grammar conventions", 84, "Strong")
            topic_row("Problem solving and data", 79, "Developing")

    with activity_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Recent learning</div>
                <div class="card-subtitle">The work behind your score growth</div>
                <div class="activity-item">
                    <div class="activity-dot"></div>
                    <div>
                        <div class="activity-title">Completed adaptive math set</div>
                        <div class="activity-detail">16 of 20 correct · Yesterday</div>
                    </div>
                </div>
                <div class="activity-item">
                    <div class="activity-dot"></div>
                    <div>
                        <div class="activity-title">Mastered punctuation boundaries</div>
                        <div class="activity-detail">Confidence increased to 88% · Monday</div>
                    </div>
                </div>
                <div class="activity-item">
                    <div class="activity-dot"></div>
                    <div>
                        <div class="activity-title">Reviewed four saved mistakes</div>
                        <div class="activity-detail">Two misconception patterns resolved · Sunday</div>
                    </div>
                </div>
                <div class="activity-item">
                    <div class="activity-dot"></div>
                    <div>
                        <div class="activity-title">Predicted score increased</div>
                        <div class="activity-detail">1380 → 1410 · Last week</div>
                    </div>
                </div>
                """
            )


# ============================================================
# PRACTICE PAGE
# ============================================================

elif page == "Practice":
    ANSWER_OPTIONS = [
        "A.  y = 2x + 3",
        "B.  y = 3x + 1",
        "C.  y = 3x − 1",
        "D.  y = 4x − 1",
    ]
    CORRECT_ANSWER = ANSWER_OPTIONS[1]

    render_html(
        """
        <div class="practice-header">
            <div class="practice-header-label">Adaptive practice</div>
            <h2>Build a session around today's needs.</h2>
            <p>
                Select a focus or let SATSam choose the highest-impact
                combination automatically.
            </p>
        </div>
        """
    )

    if not st.session_state.practice_started:
        setup_col, recommendation_col = st.columns([1.4, 1], gap="large")

        with setup_col:
            with st.container(border=True):
                render_html(
                    """
                    <div class="card-title">Session setup</div>
                    <div class="card-subtitle">
                        Customize the challenge without overthinking it
                    </div>
                    """
                )

                st.selectbox(
                    "Subject",
                    [
                        "SATSam recommendation",
                        "Math",
                        "Reading and Writing",
                        "Balanced",
                    ],
                    key="practice_subject",
                )

                st.selectbox(
                    "Primary focus",
                    [
                        "Highest-impact weakness",
                        "Linear equations",
                        "Problem solving and data",
                        "Reading inference",
                        "Grammar conventions",
                    ],
                    key="practice_focus",
                )

                st.select_slider(
                    "Starting difficulty",
                    options=[
                        "Foundation",
                        "Standard",
                        "Challenging",
                        "Test-level",
                    ],
                    value="Standard",
                    key="practice_difficulty",
                )

                st.slider(
                    "Questions",
                    min_value=5,
                    max_value=30,
                    value=12,
                    step=1,
                    key="practice_questions",
                )

                st.toggle(
                    "Explain each answer immediately",
                    value=True,
                    key="practice_explanations",
                )

                st.write("")

                if st.button(
                    "Create adaptive session →",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state.practice_started = True
                    st.session_state.answer_submitted = False
                    st.rerun()

        with recommendation_col:
            render_html(
                """
                <div class="ai-insight">
                    <div class="ai-insight-label">Recommended session</div>
                    <h3>12 questions · Mixed math</h3>
                    <p>
                        Begin with two confidence-building questions, then target
                        linear-equation accuracy under time pressure. Finish with
                        one transfer question to verify mastery.
                    </p>
                </div>
                """
            )

            with st.container(border=True):
                render_html(
                    """
                    <div class="card-title">How adaptation works</div>
                    <div class="card-subtitle">
                        More than simply making questions harder
                    </div>
                    <div class="plan-item">
                        <div class="plan-left">
                            <div class="plan-number">A</div>
                            <div>
                                <div class="plan-name">Detect the misconception</div>
                                <div class="plan-description">Sam interprets the reasoning behind errors</div>
                            </div>
                        </div>
                    </div>
                    <div class="plan-item">
                        <div class="plan-left">
                            <div class="plan-number">B</div>
                            <div>
                                <div class="plan-name">Select the next question</div>
                                <div class="plan-description">Difficulty and topic change in real time</div>
                            </div>
                        </div>
                    </div>
                    <div class="plan-item">
                        <div class="plan-left">
                            <div class="plan-number">C</div>
                            <div>
                                <div class="plan-name">Explain the pattern</div>
                                <div class="plan-description">Feedback teaches a reusable strategy</div>
                            </div>
                        </div>
                    </div>
                    """
                )

    else:
        question_col, context_col = st.columns([1.65, 0.85], gap="large")

        with question_col:
            with st.container(border=True):
                render_html(
                    """
                    <div class="question-number">Question 1 of 12 · Algebra</div>
                    <div class="question-text">
                        A line passes through the points (2, 7) and (6, 19).
                        Which equation represents the line?
                    </div>
                    <div class="formula-box">
                        Use the slope-intercept form: y = mx + b
                    </div>
                    """
                )

                def clear_feedback():
                    st.session_state.answer_submitted = False

                selected_answer = st.radio(
                    "Select one answer",
                    ANSWER_OPTIONS,
                    index=None,
                    key="selected_answer",
                    on_change=clear_feedback,
                )

                button_col_1, button_col_2 = st.columns([1, 1])

                with button_col_1:
                    if st.button("Leave session", use_container_width=True):
                        st.session_state.practice_started = False
                        st.session_state.answer_submitted = False
                        st.rerun()

                with button_col_2:
                    if st.button(
                        "Submit answer →",
                        type="primary",
                        use_container_width=True,
                        disabled=selected_answer is None,
                    ):
                        st.session_state.answer_submitted = True

                if st.session_state.answer_submitted:
                    if selected_answer == CORRECT_ANSWER:
                        st.success(
                            "Correct. You found both the slope and "
                            "the y-intercept accurately."
                        )
                    else:
                        st.error(
                            "Not quite. Your slope may be correct, but check "
                            "the substitution step used to find b."
                        )

                    render_html(
                        """
                        <div class="ai-insight">
                            <div class="ai-insight-label">Sam's explanation</div>
                            <h3>Find the slope before the intercept.</h3>
                            <p>
                                The slope is (19 − 7) ÷ (6 − 2) = 3. Substitute
                                (2, 7) into y = 3x + b: 7 = 6 + b, so b = 1.
                                Therefore, the equation is y = 3x + 1.
                            </p>
                        </div>
                        """
                    )

        with context_col:
            with st.container(border=True):
                render_html(
                    """
                    <div class="card-title">Session pulse</div>
                    <div class="card-subtitle">Live signals from your performance</div>
                    """
                )

                metric_card(
                    "Current difficulty",
                    "Standard",
                    "Adjusts after submission",
                    "◇",
                )

                st.write("")

                st.markdown("**Skill confidence**")
                st.progress(0.61)
                st.caption("61% · Linear equations")

                st.markdown("**Suggested pace**")
                st.progress(0.48)
                st.caption("About 75 seconds for this question")

            st.write("")

            render_html(
                """
                <div class="coach-quote">
                    Take ten seconds to identify what the question is really
                    testing before calculating.
                </div>
                """
            )


# ============================================================
# INSIGHTS PAGE
# ============================================================

elif page == "Insights":
    section_header(
        "Learning intelligence",
        "Your progress has a pattern",
        "SATSam combines accuracy, pacing, confidence, and mistake type.",
    )

    metrics = st.columns(4)

    with metrics[0]:
        metric_card("Predicted score", "1410", "Range: 1380–1450", "↗")

    with metrics[1]:
        metric_card("Math", "720", "+40 since baseline", "∑")

    with metrics[2]:
        metric_card("Reading & Writing", "690", "+20 since baseline", "Aa")

    with metrics[3]:
        metric_card("Pacing stability", "76%", "Improving this week", "◷")

    section_header(
        "Score trajectory",
        "Steady gains—not random swings",
        "Your projection updates as SATSam gathers more evidence.",
    )

    chart_col, summary_col = st.columns([1.65, 0.85], gap="large")

    with chart_col:
        with st.container(border=True):
            score_history = {
                "Predicted score": [1320, 1340, 1330, 1360, 1380, 1390, 1410],
                "Target score": [st.session_state.target_score] * 7,
            }

            st.line_chart(score_history, height=330)

    with summary_col:
        render_html(
            """
            <div class="ai-insight">
                <div class="ai-insight-label">Weekly diagnosis</div>
                <h3>Your math growth is accelerating.</h3>
                <p>
                    Algebra accuracy rose while your average response time fell
                    by nine seconds. Reading performance is stable, but inference
                    questions remain less consistent.
                </p>
            </div>
            """
        )

        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Score opportunity</div>
                <div class="card-subtitle">
                    Estimated points available by test day
                </div>
                """
            )

            st.metric("Realistic gain", "+70 points", "with current consistency")

            st.progress(0.63)

            st.caption("You have completed 63% of the recommended preparation.")

    section_header(
        "Skill map",
        "Where your next points are hiding",
        "Priorities are ranked by expected score impact.",
    )

    weak_col, strong_col = st.columns(2, gap="large")

    with weak_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Highest-impact opportunities</div>
                <div class="card-subtitle">Skills worth prioritizing this week</div>
                """
            )

            topic_row("Linear equations", 61, "Needs work")
            topic_row("Reading inference", 67, "Needs work")
            topic_row("Transitions", 72, "Developing")

    with strong_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Reliable strengths</div>
                <div class="card-subtitle">Skills you can trust under time pressure</div>
                """
            )

            topic_row("Punctuation boundaries", 91, "Strong")
            topic_row("Ratios and percentages", 87, "Strong")
            topic_row("Words in context", 84, "Strong")


# ============================================================
# STUDY PLAN PAGE
# ============================================================

elif page == "Study Plan":
    section_header(
        "Personalized planning",
        "Build a plan that fits real life",
        "SATSam balances urgency, weak areas, and available study time.",
    )

    settings_col, preview_col = st.columns([0.9, 1.5], gap="large")

    with settings_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Plan preferences</div>
                <div class="card-subtitle">Set realistic boundaries for your week</div>
                """
            )

            st.date_input("SAT date", key="sat_date")

            st.number_input(
                "Target score",
                min_value=400,
                max_value=1600,
                step=10,
                key="target_score",
            )

            weekday_minutes = st.slider(
                "Weekday minutes",
                min_value=15,
                max_value=120,
                step=5,
                key="weekday_minutes",
                value=45,
            )

            weekend_minutes = st.slider(
                "Weekend minutes",
                min_value=30,
                max_value=240,
                step=15,
                key="weekend_minutes",
                value=120,
            )

            st.selectbox(
                "Preferred lighter day",
                ["Friday", "Sunday", "Wednesday", "No lighter day"],
                key="rest_day",
            )

            if st.button(
                "Regenerate my plan",
                type="primary",
                use_container_width=True,
            ):
                st.success("Your plan was updated around your available time.")

    with preview_col:
        light_day = round(weekday_minutes * 0.55 / 5) * 5
        weekly_total = (weekday_minutes * 4) + light_day + weekend_minutes + 90

        render_html(
            """
            <div class="ai-insight">
                <div class="ai-insight-label">Plan strategy</div>
                <h3>Prioritize math without neglecting reading.</h3>
                <p>
                    This week allocates 55% of practice to math because it
                    currently offers the largest point return. Reading remains
                    frequent enough to preserve momentum.
                </p>
            </div>
            """
        )

        plan_left, plan_right = st.columns(2)

        with plan_left:
            render_html(
                f"""
                <div class="day-card">
                    <div class="day-name">Monday · {weekday_minutes} min</div>
                    <div class="day-task">Linear equations + guided practice</div>
                    <div class="day-detail">8-minute lesson · 15 adaptive questions</div>
                </div>
                <div class="day-card">
                    <div class="day-name">Tuesday · {weekday_minutes} min</div>
                    <div class="day-task">Reading inference and evidence</div>
                    <div class="day-detail">Two short passages · Mistake reflection</div>
                </div>
                <div class="day-card">
                    <div class="day-name">Wednesday · {weekday_minutes} min</div>
                    <div class="day-task">Timed mixed math module</div>
                    <div class="day-detail">Test pacing · Calculator strategy</div>
                </div>
                <div class="day-card">
                    <div class="day-name">Thursday · {weekday_minutes} min</div>
                    <div class="day-task">Grammar precision</div>
                    <div class="day-detail">Transitions · Sentence boundaries</div>
                </div>
                """
            )

        with plan_right:
            render_html(
                f"""
                <div class="day-card">
                    <div class="day-name">Friday · {light_day} min</div>
                    <div class="day-task">Light review and confidence set</div>
                    <div class="day-detail">Saved mistakes · Five mastered questions</div>
                </div>
                <div class="day-card">
                    <div class="day-name">Saturday · {weekend_minutes} min</div>
                    <div class="day-task">Full-length practice modules</div>
                    <div class="day-detail">Timed conditions · Automated analysis</div>
                </div>
                <div class="day-card">
                    <div class="day-name">Sunday · 90 min</div>
                    <div class="day-task">Deep mistake review</div>
                    <div class="day-detail">Diagnose patterns · Update next week's plan</div>
                </div>
                <div class="day-card">
                    <div class="day-name">Weekly outcome</div>
                    <div class="day-task">{weekly_total} focused minutes</div>
                    <div class="day-detail">105 questions · 2 timed modules</div>
                </div>
                """
            )


# ============================================================
# FOCUS TIMER PAGE
# ============================================================

elif page == "Focus Timer":
    section_header(
        "Distraction-free study",
        "One focused block at a time",
        "Use a quiet timer for practice, review, or full modules.",
    )

    timer_col, intention_col = st.columns([1.2, 0.8], gap="large")

    with timer_col:
        with st.container(border=True):
            timer_length = st.slider(
                "Session length",
                min_value=15,
                max_value=60,
                value=25,
                step=5,
                key="timer_length",
            )

            render_html(
                f"""
                <div class="progress-ring-card">
                    <div class="progress-ring" style="--progress: 0%;">
                        <div class="progress-ring-content">
                            <div class="progress-ring-value">{timer_length}:00</div>
                            <div class="progress-ring-label">focus session</div>
                        </div>
                    </div>
                </div>
                """
            )

            timer_buttons = st.columns(2)

            with timer_buttons[0]:
                if st.button(
                    "Start focus session",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state.pomodoro_running = True
                    st.success(f"{timer_length}-minute session started.")

            with timer_buttons[1]:
                if st.button("Reset", use_container_width=True):
                    st.session_state.pomodoro_running = False

            st.caption(
                "The demonstration timer can later be connected to Streamlit "
                "fragments or JavaScript for live countdowns."
            )

    with intention_col:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Set an intention</div>
                <div class="card-subtitle">
                    Define what success looks like before beginning
                </div>
                """
            )

            st.selectbox(
                "Focus activity",
                [
                    "Adaptive practice",
                    "Mistake review",
                    "Concept lesson",
                    "Timed module",
                ],
                key="focus_activity",
            )

            st.text_area(
                "Session intention",
                placeholder=(
                    "Example: Solve slowly enough to verify each "
                    "substitution step."
                ),
                height=125,
                key="session_intention",
            )

            render_html(
                """
                <div class="coach-quote">
                    A focused twenty-five minutes is more valuable than an
                    unfocused hour.
                </div>
                """
            )


# ============================================================
# SETTINGS PAGE
# ============================================================

elif page == "Settings":
    section_header(
        "Preferences",
        "Make SATSam feel like your study space",
        "Adjust your targets, session rhythm, and feedback style.",
    )

    settings_left, settings_right = st.columns(2, gap="large")

    with settings_left:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Study preferences</div>
                <div class="card-subtitle">Control how sessions are structured</div>
                """
            )

            st.slider(
                "Daily study goal",
                min_value=15,
                max_value=120,
                step=5,
                key="study_goal",
            )

            st.number_input(
                "Target SAT score",
                min_value=400,
                max_value=1600,
                step=10,
                key="target_score",
            )

            st.slider(
                "Default focus session",
                min_value=15,
                max_value=60,
                value=25,
                step=5,
                key="default_focus_length",
            )

            st.selectbox(
                "Default practice mode",
                [
                    "SATSam recommendation",
                    "Balanced",
                    "Math",
                    "Reading and Writing",
                ],
                key="default_practice_mode",
            )

    with settings_right:
        with st.container(border=True):
            render_html(
                """
                <div class="card-title">Coaching preferences</div>
                <div class="card-subtitle">Choose how Sam communicates feedback</div>
                """
            )

            st.selectbox(
                "Explanation style",
                [
                    "Concise and strategic",
                    "Step-by-step",
                    "Socratic questions",
                    "Detailed tutor mode",
                ],
                key="explanation_style",
            )

            st.selectbox(
                "Coach personality",
                [
                    "Warm and focused",
                    "Direct and challenging",
                    "Calm and encouraging",
                ],
                key="coach_personality",
            )

            st.toggle("Show hints before explanations", value=True, key="show_hints")
            st.toggle("Include timing feedback", value=True, key="timing_feedback")
            st.toggle("Send daily study reminder", value=False, key="daily_reminder")

    st.write("")

    if st.button("Save preferences", type="primary"):
        st.success("Your SATSam preferences have been saved.")