# Dear Diary — Design Documentation

This document outlines the design choices, technical stack, and potential future enhancements for **Dear Diary**, a personal AI journaling companion developed for the hackathon. The application prioritises user privacy through local encryption while offering optional AI-powered reflection and prompts.

---

## 1. Overview and Goals

Dear Diary is a web-based journaling application that allows users to write daily entries, view insights (calendar, mood, recurring themes), and optionally use an AI persona (“Diary”) to generate weekly reflections and journal prompts from their own entries. The primary design goal is **privacy-first**: entry content is encrypted at rest and only decryptable with a user-chosen passphrase. AI features are opt-in and clearly disclosed so users understand when their data is sent to an external service.

---

## 2. Design Choices

### 2.1 Architecture

The application follows a simple modular structure suitable for a single developer or small team:

- **Entry point** (`app.py`): Streamlit page config, CSS injection, session state initialisation, vault check, and tab routing. All high-level flow (unlock → journal/insights/reflection/settings) is centralised here.
- **Pages** (`pages/`): One module per tab—Journal, Insights, Reflection, Settings. Each exposes a `render()` function called by the main app when that tab is active. This keeps UI logic separated by concern and makes it easy to add or remove tabs.
- **Data and crypto** (`db.py`, `crypto.py`, `auth.py`): Database access is wrapped in a `_with_conn` pattern so connections are always closed; entry content is encrypted before write and decrypted on read using a key derived from the user’s passphrase. Auth handles vault setup, unlock, lock, and reset without storing the passphrase.
- **AI and sentiment** (`llm.py`, `sentiment.py`): LLM calls and prompt/reflection logic live in `llm.py`; sentiment and theme extraction (used for mood labels and recurring-themes chart) are in `sentiment.py`. This separation allows the app to function fully without an API key; AI is an optional layer.

This structure was chosen for clarity and maintainability under time constraints, rather than for scalability (e.g. no separate backend service or API).

### 2.2 Security and Privacy

- **Encryption**: Entry text is encrypted with **AES-GCM** (via the `cryptography` library). A random IV is generated per encryption. The key is derived from the user’s passphrase using **PBKDF2-HMAC-SHA256** with 250,000 iterations and a random salt stored in the vault table. Only the ciphertext and IV are stored in SQLite; the key exists in memory only while the vault is unlocked.
- **Vault**: A single “vault” row stores salt and a test ciphertext. On unlock, the app derives the key, decrypts the test value, and keeps the key in a process-local variable. Locking clears the key so entry content cannot be read until the user unlocks again. This gives a simple “lock before leaving” model for shared machines.
- **AI and sensitive files**: When AI is enabled, the cached reflection and last-shown prompt are stored in encrypted JSON files (using the same vault key) so that even on disk they are not readable without the passphrase. The OpenAI API key is loaded from environment (or `.env`) and never exposed in the UI.
- **User communication**: The app states clearly when AI is enabled that “your data can be read by OpenAI,” so the privacy trade-off is explicit.

### 2.3 Data Model and Storage

- **SQLite** was chosen for simplicity and portability: a single `journal.db` file holds all entries and vault metadata, with no separate server. The `entries` table stores encrypted content, IV, sentiment score/label, and themes (JSON array). The `vault` table holds salt and test cipher/IV. Indexes on `created_at` and `sentiment_score` support calendar and sentiment queries.
- **Entry IDs** are generated with a timestamp plus a random suffix (`os.urandom(4).hex()`) to avoid collisions when many entries are imported in one go (e.g. restore from export).
- **Themes** are extracted locally via frequency counts over tokenised words, with standard and journal-specific stopwords removed so the recurring-themes chart emphasises meaningful terms rather than filler (“day,” “today,” “things,” etc.).

### 2.4 AI Integration

- **Optional by design**: The app works fully without an API key: generic prompts and no AI reflection. “Use AI” in Settings toggles the Diary feature; the key is read from `OPENAI_API_KEY` in the environment.
- **Single AI role**: “Diary” is the only AI persona: it produces a weekly reflection (150–200 words) and 2–4 follow-up journal prompts from the user’s last seven days of entries. The system prompt instructs a warm, non-judgmental tone and forbids inventing events or giving unsolicited advice. Output format is constrained (reflection block then `PROMPTS:` with bullet lines) so parsing is reliable.
- **Prompt flow**: If a stored AI reflection with prompts exists, the Journal tab shows one of those prompts (rotated hourly or on “Get another prompt”); otherwise it shows one of the built-in generic prompts. No time-of-day logic—just “current saved/rotated prompt” for simplicity.
- **Caching**: The last-shown prompt and the AI reflection (including its prompts) are cached (encrypted) so the app does not call the API on every page load. Reflection is regenerated when the user requests it or when the app opens and the stored reflection is from a previous day.

### 2.5 User Experience

- **Tabs**: Journal (prompt + entry), Insights (calendar + themes), Reflection (AI “week in reflection” when enabled), Settings (AI toggle, export/import, delete). Lock is always visible when unlocked so users can lock before stepping away.
- **Streak**: Consecutive days with at least one entry; counted from today if today has an entry, else from yesterday, so the number reflects “current streak” rather than “days since last entry.”
- **Export/import**: Full export as JSON (content, timestamps, sentiment, themes) and import that merges by day (same-day content can be concatenated). This supports backup and migration (e.g. after changing passphrase or resetting data).

---

## 3. Technical Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.10+ |
| **UI** | Streamlit (>=1.28.0) |
| **Database** | SQLite 3 (via `sqlite3`) |
| **Encryption** | `cryptography`: AES-GCM (AEAD), PBKDF2-HMAC-SHA256 |
| **Sentiment** | VADER (`vaderSentiment` >=3.3.2) for compound score and positive/neutral/negative label |
| **AI** | OpenAI API; model: **gpt-4.1-nano** (reflection + prompts) |
| **Config** | `python-dotenv` for `.env` (e.g. `OPENAI_API_KEY`) |
| **Styling** | Custom CSS injected via `styles.css` |

Dependencies are pinned in `requirements.txt`. No front-end framework beyond Streamlit; no separate backend—Streamlit drives both UI and logic.

---

## 4. Potential Future Enhancements

- **Offline / local LLM**: Support an optional local model (e.g. via Ollama or a small fine-tuned model) so users can get reflection and prompts without sending data to OpenAI. Would require a small abstraction over “prompt → response” so the same UI can drive either API or local inference.
- **Multi-device sync**: End-to-end encrypted sync (e.g. encrypted blobs in a user-owned store) so the same journal can be used across devices without a central server reading content.
- **Richer insights**: Trend lines for sentiment over time, simple NLP summaries (e.g. key phrases per week) without LLM, or optional tagging/categories for entries.
- **Accessibility and i18n**: Screen-reader-friendly labels, keyboard navigation, and localisation so the app can be used in multiple languages.
- **Stronger auth**: Optional 2FA or hardware-key support for vault unlock, or a “forgot passphrase” flow that only restores from an exported backup (no back door).
- **Reflection scheduling**: Let users set “generate reflection on Mondays” or after N new entries instead of only on app open or manual button.
- **Prompt customisation**: Allow users to add or edit their own generic prompts in Settings so the Journal tab can mix built-in and personal prompts when AI is off.

These are noted as directions for future work rather than commitments; the current design keeps the scope manageable for the hackathon while leaving room for such extensions.
