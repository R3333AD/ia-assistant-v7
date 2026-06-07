"""
Historique des conversations en SQLite.
Une session = 1 ligne dans `sessions`, N messages dans `messages`.
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sessions.db")


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                persona TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                thoughts_json TEXT,
                image_path TEXT,
                ts TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, id)")


def new_session(name: str = None, persona: str = "") -> str:
    sid = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat(timespec="seconds")
    if not name:
        name = f"Session {datetime.now().strftime('%d/%m %H:%M')}"
    with _conn() as c:
        c.execute(
            "INSERT INTO sessions (id, name, persona, created_at, updated_at) VALUES (?,?,?,?,?)",
            (sid, name, persona, now, now),
        )
    return sid


def rename_session(sid: str, name: str) -> None:
    with _conn() as c:
        c.execute("UPDATE sessions SET name=?, updated_at=? WHERE id=?", (name, datetime.now().isoformat(timespec="seconds"), sid))


def touch_session(sid: str) -> None:
    with _conn() as c:
        c.execute("UPDATE sessions SET updated_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), sid))


def add_message(sid: str, role: str, content: str, thoughts: list = None, image_path: str = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO messages (session_id, role, content, thoughts_json, image_path, ts) VALUES (?,?,?,?,?,?)",
            (sid, role, content, json.dumps(thoughts or [], ensure_ascii=False), image_path, datetime.now().isoformat(timespec="seconds")),
        )
        c.execute("UPDATE sessions SET updated_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), sid))


def get_messages(sid: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content, thoughts_json, image_path, ts FROM messages WHERE session_id=? ORDER BY id",
            (sid,),
        ).fetchall()
    out = []
    for r in rows:
        try:
            thoughts = json.loads(r["thoughts_json"]) if r["thoughts_json"] else None
        except Exception:
            thoughts = None
        out.append({
            "role": r["role"],
            "content": r["content"],
            "thoughts": thoughts,
            "image_used": r["image_path"],
            "ts": r["ts"],
        })
    return out


def list_sessions(limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT s.id, s.name, s.persona, s.created_at, s.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS msg_count
            FROM sessions s
            ORDER BY s.updated_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def delete_session(sid: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        c.execute("DELETE FROM sessions WHERE id=?", (sid,))


def save_summary(sid: str, summary: str) -> None:
    with _conn() as c:
        c.execute("UPDATE sessions SET summary=? WHERE id=?", (summary, sid))


def get_summary(sid: str) -> str:
    with _conn() as c:
        row = c.execute("SELECT summary FROM sessions WHERE id=?", (sid,)).fetchone()
        return row["summary"] if row and row["summary"] else ""


def migrate_add_summary():
    with _conn() as c:
        try:
            c.execute("ALTER TABLE sessions ADD COLUMN summary TEXT DEFAULT ''")
        except Exception:
            pass  # already exists


migrate_add_summary()
init_db()
