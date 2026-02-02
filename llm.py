# OpenAI integration, prompts, reflection (local + AI).
import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

import crypto
import sentiment

load_dotenv(Path(__file__).resolve().parent / ".env")
STORAGE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = STORAGE_DIR / ".llm_config.json"
REFLECTION_PATH = STORAGE_DIR / ".ai_reflection.json"
ROTATE_AFTER_MS = 1000 * 60 * 60

GENERIC_PROMPTS = [
    "What's one small win from today?",
    "What are you grateful for?",
    "How are you feeling?",
    "What would make tomorrow better?",
    "What felt alive in you today?",
    "What's on your mind right now?",
    "What would you tell your past self from this week?",
    "What do you need to hear today?",
    "What are you proud of lately?",
    "What's one thing you'd do differently if you could?",
    "Who or what supported you recently?",
    "What are you looking forward to?",
    "What felt hard today—and what helped?",
    "What would rest look like for you right now?",
]


def get_server_api_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY") or None


def _config():
    try:
        return json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    except Exception:
        return {}


def get_use_ai() -> bool:
    return _config().get("useAi", False)


def set_use_ai(value: bool) -> None:
    c = _config()
    c["useAi"] = bool(value)
    CONFIG_PATH.write_text(json.dumps(c, indent=2))


def clear_all_llm_keys() -> None:
    c = _config()
    c.pop("useAi", None)
    CONFIG_PATH.write_text(json.dumps(c, indent=2))


# Read/decrypt JSON from path; returns dict or None.
def _read_encrypted(path: Path) -> dict | None:
    key = crypto.get_key()
    if not key or not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        if "ciphertext" not in raw or "iv" not in raw:
            return None
        plain = crypto.decrypt(raw["ciphertext"], raw["iv"], key)
        return json.loads(plain)
    except Exception:
        return None


# Encrypt and write data as JSON to path.
def _write_encrypted(path: Path, data: dict) -> None:
    key = crypto.get_key()
    if not key:
        raise ValueError("Unlock required to save.")
    plain = json.dumps(data, indent=2)
    ciphertext, iv = crypto.encrypt(plain, key)
    path.write_text(json.dumps({"ciphertext": ciphertext, "iv": iv}))


def _last_prompt():
    p = STORAGE_DIR / ".journal_last_prompt.json"
    pt = STORAGE_DIR / ".journal_last_prompt_ts.json"
    # Prefer encrypted single file
    d = _read_encrypted(p)
    if d is not None and "text" in d and "ts" in d:
        return {"text": d["text"], "ts": int(d["ts"])}
    # Legacy: plain .json + .ts
    try:
        if p.exists() and pt.exists():
            return {"text": json.loads(p.read_text()), "ts": int(pt.read_text().strip())}
    except Exception:
        pass
    return None


def _set_prompt(text: str) -> None:
    try:
        data = {"text": text, "ts": int(time.time() * 1000)}
        _write_encrypted(STORAGE_DIR / ".journal_last_prompt.json", data)
        # Remove legacy ts file if present
        pt = STORAGE_DIR / ".journal_last_prompt_ts.json"
        if pt.exists():
            pt.unlink()
    except Exception:
        pass


def _pick(arr, exclude=None):
    f = [x for x in arr if x != exclude] if exclude else arr
    return random.choice(f) if f else (arr[0] if arr else "")


# Return saved AI prompt or generic; rotates hourly unless force_new.
def get_prompt(force_new: bool = False) -> str:
    stored = get_stored_reflection()
    raw = (stored.get("prompts") or []) if stored else []
    ai_list = raw if isinstance(raw, list) else ((raw.get("afternoon") or []) + (raw.get("evening") or []))
    last = _last_prompt()
    now_ms = int(time.time() * 1000)
    rotate = force_new or not last or (now_ms - last["ts"] > ROTATE_AFTER_MS)
    if ai_list:
        if rotate:
            chosen = _pick(ai_list, last.get("text") if last else None)
        elif last and last["text"] in ai_list:
            chosen = last["text"]
        else:
            chosen = _pick(ai_list, None)
    else:
        chosen = _pick(GENERIC_PROMPTS, last.get("text") if last else None) if rotate else (last["text"] if last else _pick(GENERIC_PROMPTS, None))
    if rotate or (ai_list and (not last or last["text"] not in ai_list)) or (not ai_list and not last):
        _set_prompt(chosen)
    return chosen


def get_period_range(period: str) -> tuple[int, int]:
    end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
    start = (end - timedelta(days=6 if period == "week" else 29)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def generate_reflection_summary(entries: list, period: str) -> dict:
    start_ms, end_ms = get_period_range(period)
    in_range = [e for e in entries if start_ms <= e.get("createdAt", 0) <= end_ms]
    prev_start, prev_end = start_ms - (end_ms - start_ms + 1), start_ms - 1
    prev_entries = [e for e in entries if prev_start <= e.get("createdAt", 0) <= prev_end]
    agg = sentiment.aggregate_themes(in_range)
    top_themes = [a["theme"] for a in agg[:5]]

    def avg_score(arr):
        with_s = [e for e in arr if e.get("sentimentScore") is not None]
        return sum(e["sentimentScore"] for e in with_s) / len(with_s) if with_s else 0

    diff = avg_score(in_range) - avg_score(prev_entries)
    trend = "up" if diff > 0.3 else ("down" if diff < -0.3 else "stable")
    highlights = []
    if top_themes:
        highlights.append(f"You wrote often about: {', '.join(top_themes[:3])}.")
    if trend == "up":
        highlights.append("Your entries tended to be more positive than the previous period.")
    elif trend == "down":
        highlights.append("Your entries reflected more difficult moments. Journaling can help process them.")
    pos = [e for e in in_range if e.get("sentimentLabel") == "positive"]
    if 0 < len(pos) <= 3:
        tp = sentiment.aggregate_themes(pos)[:2]
        if tp:
            highlights.append(f"You felt better when writing about: {' and '.join(a['theme'] for a in tp)}.")
    if not highlights:
        highlights.append("Keep writing—patterns become clearer over time.")
    return {"period": period, "startDate": start_ms, "endDate": end_ms, "sentimentTrend": trend, "topThemes": top_themes, "highlights": highlights, "generatedAt": int(datetime.now().timestamp() * 1000)}


def _system_prompt(n_days: int) -> str:
    return f"""You are Diary, the user's private journaling companion. Your voice is warm, calm, and non-judgmental. You never lecture or give unsolicited advice.

Using their journal entries from the past {n_days} days only:
1. REFLECTION (150–200 words): Write a short reflection spoken directly to them ("you"). Acknowledge what showed up—themes, moods, small wins or struggles—without sugarcoating or pushing positivity. Notice patterns or progress only when they're clearly there. End with something that feels like a gentle nod, not a lesson.

2. PROMPTS: On a new line write exactly "PROMPTS:" then list 2–4 short journal prompts based on their reflection (one per line, each starting with "- "). Each prompt should be a single open-ended question or invitation (one line only), e.g. "What felt alive in you today?" or "What would you tell your past self from this week?" No greetings or extra text in the prompts.

Output format: reflection text first, then a blank line, then "PROMPTS:" and the bullet list. Use only the entries provided; do not invent events or dates."""


def _build_user_prompt(entries: list, n_days: int) -> str:
    lines = []
    for e in sorted(entries, key=lambda x: x.get("createdAt", 0)):
        ts = e.get("createdAt", 0) / 1000.0
        lines.append(f"[{datetime.fromtimestamp(ts).strftime('%a, %b %d, %Y')}]\n{e.get('content', '')}")
    return f"Entries from the past {n_days} days:\n\n" + "\n\n---\n\n".join(lines) + "\n\nWrite the reflection and PROMPTS as specified."


def _parse_reflection(raw: str) -> dict:
    idx = raw.find("PROMPTS:")
    reflection = raw[:idx].strip() if idx >= 0 else raw.strip()
    prompts = []
    if idx >= 0:
        rest = raw[idx + len("PROMPTS:"):].strip()
        prompts = [re.sub(r"^\s*-\s*", "", line).strip() for line in rest.split("\n") if line.strip()]
    return {"reflection": reflection, "prompts": prompts}


def _call_openai(api_key: str, system: str, user: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        r = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=800,
        )
        text = (r.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("Empty response")
        return text
    except Exception as e:
        raise RuntimeError(str(e))


def generate_reflection_with_llm(entries: list) -> dict:
    key = get_server_api_key()
    if not key:
        raise ValueError("OpenAI API key not set. Set OPENAI_API_KEY in .env or environment.")
    raw = _call_openai(key, _system_prompt(7), _build_user_prompt(entries, 7))
    return _parse_reflection(raw)


def get_stored_reflection() -> dict | None:
    d = _read_encrypted(REFLECTION_PATH)
    if d is not None and "reflection" in d and "prompts" in d:
        if isinstance(d.get("prompts"), (list, dict)):
            return d
    if REFLECTION_PATH.exists():
        try:
            d = json.loads(REFLECTION_PATH.read_text())
            if "reflection" in d and "prompts" in d and isinstance(d.get("prompts"), (list, dict)):
                return d
        except Exception:
            pass
    return None


def set_stored_reflection(payload: dict):
    now = datetime.now()
    data = {
        "reflection": payload["reflection"],
        "prompts": payload["prompts"],
        "generatedAt": int(now.timestamp() * 1000),
        "generatedDate": now.strftime("%Y-%m-%d"),
    }
    _write_encrypted(REFLECTION_PATH, data)


def clear_stored_reflections():
    if REFLECTION_PATH.exists():
        REFLECTION_PATH.unlink()
