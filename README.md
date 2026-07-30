# SATSam

A warm, adaptive SAT coach that runs entirely on your own machine. SATSam draws
real practice questions from a local bank, adapts difficulty after every answer,
and uses a **local** Ollama model (nothing leaves your computer) to explain
mistakes, diagnose *why* an answer went wrong, and generate a realistic weekly
study plan around the time you actually have.

Built with Streamlit.

---

## Project structure

The app used to live in one large file. It is now split into small, focused
modules so each concern is easy to find and change.

```
satsam/
├── app.py                     # Entry point: wires everything together and routes pages
├── requirements.txt
├── README.md
├── .gitignore
├── data/
│   └── sat-questions.json     # The question bank (a small sample ships here)
└── src/
    ├── config.py              # Constants + session-state defaults
    ├── paths.py               # Filesystem locations
    ├── html_utils.py          # Raw-HTML helpers for Streamlit
    ├── data_loader.py         # Loads the question bank (cached)
    ├── settings_store.py      # Saves / loads preferences
    ├── metrics.py             # Stats derived from answer history
    ├── helpers.py             # Small presentation helpers (dates, greeting, etc.)
    ├── questions.py           # Adaptive question selection + answer checking
    ├── state.py               # Session-state setup + practice-session lifecycle
    ├── styles.py              # The global stylesheet
    ├── ai/                    # Sam, the local-model tutor
    │   ├── client.py          #   Ollama transport + JSON parsing
    │   ├── prompts.py         #   System prompts + question formatting
    │   ├── explanations.py    #   Per-answer coaching explanations
    │   ├── fingerprint.py     #   The AI Error Fingerprint (diagnosis + card)
    │   ├── coaching.py        #   Focus-skill targeting + session review
    │   └── study_plan.py      #   The validated 7-day study plan
    ├── components/            # Reusable UI
    │   ├── common.py          #   Metric cards, section headers, topic rows
    │   ├── timer.py           #   The persistent focus timer (full + mini)
    │   ├── chat.py            #   "Chat with Sam" dialog + floating launcher
    │   └── sidebar.py         #   The left sidebar
    └── views/                 # One module per page
        ├── home.py
        ├── practice.py
        ├── insights.py
        ├── study_plan.py
        ├── focus_timer.py
        └── settings.py
```

**How it fits together:** `app.py` calls `st.set_page_config` first, then seeds
session state, injects the stylesheet, draws the sidebar (which reports the
selected page), mounts the chat launcher, and finally calls the matching
`views/<page>.render()`. Modules only run Streamlit commands when a `render`
function is *called*, never at import time — that is what keeps
`set_page_config` safely first.

---

## Running locally

Requires Python 3.9+ and (for the AI features) [Ollama](https://ollama.com)
running locally.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional, for AI features) start Ollama and pull a model
ollama pull qwen3:8b

# 3. Run the app
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

The AI tutor is optional: with it off, the app still runs practice, insights,
the timer, and a heuristic Error Fingerprint. Turn it on under **Settings**.

### Your question bank

`data/sat-questions.json` ships with a small sample so the app runs immediately.
Replace it with your full bank using the same shape:

```json
{
  "questions": [
    {
      "id": "unique-id",
      "section": "math",            // "math" | "reading_writing"
      "domain": "Algebra",
      "skill": "Linear equations in one variable",
      "difficulty": "easy",          // "easy" | "medium" | "hard"
      "format": "mcq",               // "mcq" | "spr"
      "stimulus": "optional passage/context",
      "prompt": "The question text",
      "choices": [{"id": "A", "text": "..."}],   // mcq only
      "correct": "B",                 // choice id, or the numeric answer for spr
      "distractors": {"A": "why A is tempting"},  // optional, mcq only
      "explanation": "reference explanation",
      "estimated_seconds": 60
    }
  ]
}
```

---

## Putting this into VSCode and pushing to GitHub

Everything is plain text, so this is just files-in-folders — no build step.

**Option A — you already have the repo cloned locally**

1. Open your repo folder in VSCode.
2. Recreate the folders and files exactly as shown in *Project structure* above.
   (If you downloaded the zip, drag its contents into the repo root.)
3. Move your existing full question bank to `data/sat-questions.json`.
4. Delete the old single-file app.
5. In the VSCode terminal:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py       # confirm it works
   git add .
   git commit -m "Refactor into modular package + UI polish"
   git push
   ```

**Option B — fresh start from the zip**

1. Unzip `satsam.zip`.
2. `File → Open Folder…` and pick the unzipped `satsam` folder.
3. Drop your full question bank into `data/sat-questions.json`.
4. In the terminal:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
5. If this is a new repo:
   ```bash
   git init
   git add .
   git commit -m "Initial modular SATSam"
   git branch -M main
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

**Two things worth checking**

- Run `streamlit run app.py` from the repo root (the folder that contains
  `app.py`). The imports are package-relative (`from src...`), so running from
  elsewhere will not resolve them.
- `satsam-settings.json` and `satsam-progress.json` are runtime files and are
  already in `.gitignore` — don't commit them.
