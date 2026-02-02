# SQLite: schema, entries, vault, date helpers. Use _with_conn for DB access.
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import crypto

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "journal.db"
MS_DAY_MS = 24 * 60 * 60 * 1000
ENTRY_ID_PREFIX = "entry_"
ENTRIES_COLS = "id, created_at, encrypted_content, iv, sentiment_score, sentiment_label, themes"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _with_conn(f):
    conn = get_conn()
    try:
        return f(conn)
    finally:
        conn.close()


def init_db():
    def run(c):
        c.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                encrypted_content TEXT NOT NULL,
                iv TEXT NOT NULL,
                sentiment_score REAL,
                sentiment_label TEXT,
                themes TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_entries_created_at ON entries(created_at);
            CREATE INDEX IF NOT EXISTS idx_entries_sentiment ON entries(sentiment_score);
            CREATE TABLE IF NOT EXISTS vault (
                id TEXT PRIMARY KEY, salt TEXT NOT NULL, test_cipher TEXT NOT NULL, test_iv TEXT NOT NULL
            );
        """)
        c.commit()
        # Migration: drop plain-text content column if present (all data must be encrypted)
        try:
            info = c.execute("PRAGMA table_info(entries)").fetchall()
            col_names = [row[1] for row in info]
            if "content" in col_names:
                c.execute("ALTER TABLE entries DROP COLUMN content")
                c.commit()
        except sqlite3.OperationalError:
            pass
    _with_conn(run)


def get_day_start_ms(ts_ms: int) -> int:
    dt = datetime.fromtimestamp(ts_ms / 1000.0)
    return int(dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)


def get_vault():
    def run(c):
        row = c.execute("SELECT id, salt, test_cipher, test_iv FROM vault WHERE id = 'vault'").fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "salt": row["salt"],
            "testCipher": row["test_cipher"],
            "testIv": row["test_iv"],
        }
    return _with_conn(run)


def set_vault(row):
    def run(c):
        c.execute("INSERT OR REPLACE INTO vault (id, salt, test_cipher, test_iv) VALUES (?, ?, ?, ?)",
                  (row["id"], row["salt"], row["testCipher"], row["testIv"]))
        c.commit()
    _with_conn(run)


def delete_vault():
    def run(c):
        c.execute("DELETE FROM vault WHERE id = 'vault'")
        c.commit()
    _with_conn(run)


def _row_dict(row):
    return {k: row[k] for k in row.keys()} if hasattr(row, "keys") else dict(row)


def _stored_to_entry(row) -> dict:
    r = _row_dict(row) if not isinstance(row, dict) else row
    key = crypto.get_key()
    if not key:
        raise ValueError("Unlock required to read entries.")
    if not (r.get("encrypted_content") and r.get("iv")):
        raise ValueError("Entry is missing encrypted data.")
    content = crypto.decrypt(r["encrypted_content"], r["iv"], key)
    return {
        "id": r["id"],
        "content": content,
        "createdAt": r["created_at"],
        "mood": r.get("mood"),
        "sentimentScore": r.get("sentiment_score"),
        "sentimentLabel": r.get("sentiment_label"),
        "themes": json.loads(r["themes"]) if r.get("themes") else None,
    }


def _encrypt_content(content: str) -> tuple[str, str]:
    key = crypto.get_key()
    if not key:
        raise ValueError("Unlock required to save entries.")
    return crypto.encrypt(content.strip(), key)


# Unique entry id; random suffix avoids collisions on import.
def _eid():
    return f"{ENTRY_ID_PREFIX}{int(time.time() * 1000)}_{os.urandom(4).hex()}"


def _save_new(conn, eid, created, enc, iv, score, label, themes_json):
    conn.execute(
        "INSERT INTO entries (id, created_at, encrypted_content, iv, sentiment_score, sentiment_label, themes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (eid, created, enc, iv, score, label, themes_json),
    )
    conn.commit()


def create_entry(content: str, meta: dict | None = None) -> dict:
    meta = meta or {}
    enc, iv = _encrypt_content(content.strip())
    eid, created = _eid(), int(time.time() * 1000)
    themes_json = json.dumps(meta.get("themes") or [])

    def run(c):
        _save_new(c, eid, created, enc, iv, meta.get("sentimentScore"), meta.get("sentimentLabel"), themes_json)
    _with_conn(run)
    return {"id": eid, "content": content.strip(), "createdAt": created, **meta}


def insert_entry(entry: dict) -> dict:
    enc, iv = _encrypt_content(entry["content"].strip())
    eid = _eid()
    created = entry.get("createdAt", int(time.time() * 1000))
    themes_json = json.dumps(entry.get("themes") or [])

    def run(c):
        _save_new(c, eid, created, enc, iv, entry.get("sentimentScore"), entry.get("sentimentLabel"), themes_json)
    _with_conn(run)
    return {"id": eid, "content": entry["content"].strip(), "createdAt": created, **entry}


def update_entry(eid: str, updates: dict) -> None:
    def run(c):
        if "content" in updates and updates["content"] is not None:
            enc, iv = _encrypt_content(updates["content"])
            c.execute("UPDATE entries SET encrypted_content = ?, iv = ? WHERE id = ?", (enc, iv, eid))
        rest = {k: v for k, v in updates.items() if k != "content" and v is not None}
        if rest:
            args, sets = [], []
            if "sentimentScore" in rest:
                sets.append("sentiment_score = ?")
                args.append(rest["sentimentScore"])
            if "sentimentLabel" in rest:
                sets.append("sentiment_label = ?")
                args.append(rest["sentimentLabel"])
            if "themes" in rest:
                sets.append("themes = ?")
                args.append(json.dumps(rest["themes"]))
            if sets:
                args.append(eid)
                c.execute(f"UPDATE entries SET {', '.join(sets)} WHERE id = ?", args)
        c.commit()
    _with_conn(run)


def delete_entry(eid: str) -> None:
    def run(c):
        c.execute("DELETE FROM entries WHERE id = ?", (eid,))
        c.commit()
    _with_conn(run)


def _entries_from_rows(rows):
    return [_stored_to_entry(_row_dict(r)) for r in rows]


def _entries_query(sql, params=()):
    def run(c):
        return _entries_from_rows(c.execute(sql, params).fetchall())
    return _with_conn(run)


def get_entry(eid: str) -> dict | None:
    def run(c):
        row = c.execute(f"SELECT {ENTRIES_COLS} FROM entries WHERE id = ?", (eid,)).fetchone()
        return None if not row else _stored_to_entry(_row_dict(row))
    return _with_conn(run)


def get_entries_by_date_range(start_ms: int, end_ms: int) -> list:
    sql = f"SELECT {ENTRIES_COLS} FROM entries WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC"
    return _entries_query(sql, (start_ms, end_ms))


def get_recent_entries(limit: int) -> list:
    return _entries_query(f"SELECT {ENTRIES_COLS} FROM entries ORDER BY created_at DESC LIMIT ?", (limit,))


def get_all_entries() -> list:
    return _entries_query(f"SELECT {ENTRIES_COLS} FROM entries ORDER BY created_at DESC")


def get_write_dates() -> list:
    def run(c):
        rows = c.execute("SELECT created_at FROM entries").fetchall()
        seen = set()
        for r in rows:
            dt = datetime.fromtimestamp(r["created_at"] / 1000.0)
            seen.add(int(dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000))
        return sorted(seen, reverse=True)
    return _with_conn(run)


def clear_all_entries() -> None:
    def run(c):
        c.execute("DELETE FROM entries")
        c.commit()
    _with_conn(run)
