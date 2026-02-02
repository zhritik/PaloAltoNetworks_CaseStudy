# Dear Diary

A personal AI journaling companion. Write daily entries, see insights and recurring themes, and optionally use **Diary** (AI) for prompts and weekly reflections. Your data is encrypted and only you can read it.

---

## Demo

**[Watch a demo](https://drive.google.com/file/d/1HGU4OjAGPOQ8fZqHDcEw4DzgcVCJGDcG/view?usp=drive_link)** — replace `YOUR_VIDEO_ID` with your video ID, or paste your full demo link here.

---

## Installation

1. **Clone or download** the project and open a terminal in the project folder.

2. **Create and activate a virtual environment** (recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **(Optional) Enable AI** — To use Diary for reflections and journal prompts:
   - Copy `.env.example` to `.env` and set your OpenAI API key:
     ```env
     OPENAI_API_KEY=sk-your-key-here
     ```
   - Or set the `OPENAI_API_KEY` environment variable. The app works without it; you’ll just use generic prompts and no AI reflection.

---

## How to run

From the project folder (with your venv activated if you use one):

```bash
streamlit run app.py
```

Open the URL shown in the terminal (e.g. `http://localhost:8501`).

---

## How to use

- **First time:** Set a passphrase (at least 8 characters). This encrypts all your entries. You’ll need it each time you open the app.
- **Journal:** See today’s prompt, write your entry, and save. Use “Get another prompt” for a different question. With AI on, Diary can generate prompts and a weekly reflection from your entries.
- **Insights:** Calendar view of days you wrote, with mood; click a date to view or edit that day. Recurring themes appear as a bar chart.
- **Reflection:** With AI on, generate “Your week in reflection” from your last 7 days of entries.
- **Settings:** Toggle **Use AI**, export/import entries as JSON, or delete all data. Use **Lock** (top-right) before leaving on a shared device.

---

**Requirements:** Python 3.10+
