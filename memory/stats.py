import os
import sqlite3
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sessions.db")


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS stats_tool_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                session_id TEXT,
                called_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS stats_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                ts TEXT NOT NULL
            )
        """)


def track_tool_call(tool_name: str, session_id: str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO stats_tool_calls (tool_name, session_id, called_at) VALUES (?,?,?)",
            (tool_name, session_id, datetime.now().isoformat(timespec="seconds")),
        )


def track_message(session_id: str, role: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO stats_messages (session_id, role, ts) VALUES (?,?,?)",
            (session_id, role, datetime.now().isoformat(timespec="seconds")),
        )


def get_tool_stats(days: int = 7) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT tool_name, COUNT(*) as count
            FROM stats_tool_calls
            WHERE called_at >= datetime('now', ?)
            GROUP BY tool_name
            ORDER BY count DESC
        """, (f"-{days} days",)).fetchall()
    return [dict(r) for r in rows]


def get_tool_timeline(days: int = 7) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT date(called_at) as day, COUNT(*) as count
            FROM stats_tool_calls
            WHERE called_at >= datetime('now', ?)
            GROUP BY day
            ORDER BY day
        """, (f"-{days} days",)).fetchall()
    return [dict(r) for r in rows]


def get_message_timeline(days: int = 7) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT date(ts) as day, role, COUNT(*) as count
            FROM stats_messages
            WHERE ts >= datetime('now', ?)
            GROUP BY day, role
            ORDER BY day
        """, (f"-{days} days",)).fetchall()
    return [dict(r) for r in rows]


def get_summary() -> dict:
    with _conn() as c:
        total_tools = c.execute("SELECT COUNT(*) as n FROM stats_tool_calls").fetchone()["n"]
        total_msgs = c.execute("SELECT COUNT(*) as n FROM stats_messages").fetchone()["n"]
        total_sessions = c.execute("SELECT COUNT(DISTINCT session_id) as n FROM stats_messages").fetchone()["n"]
        top_tool = c.execute("""
            SELECT tool_name, COUNT(*) as n FROM stats_tool_calls
            GROUP BY tool_name ORDER BY n DESC LIMIT 1
        """).fetchone()
        today = date.today().isoformat()
        msgs_today = c.execute(
            "SELECT COUNT(*) as n FROM stats_messages WHERE date(ts) = ?", (today,)
        ).fetchone()["n"]
        unique = len([r for r in c.execute("SELECT DISTINCT tool_name FROM stats_tool_calls")])
    return {
        "total_tools": total_tools,
        "total_messages": total_msgs,
        "total_sessions": total_sessions,
        "top_tool": dict(top_tool) if top_tool else {"tool_name": "-", "n": 0},
        "messages_today": msgs_today,
        "unique_tools": unique,
    }


init_db()
