import os
import sqlite3
import uuid
import json
import subprocess
import threading
import time
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sessions.db")
_scheduler = None
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                prompt TEXT,
                cron TEXT NOT NULL,
                action TEXT DEFAULT 'message',
                webhook_name TEXT,
                script_path TEXT,
                message TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS task_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                ran_at TEXT NOT NULL,
                result TEXT,
                success INTEGER DEFAULT 1,
                FOREIGN KEY (task_id) REFERENCES scheduled_tasks(id)
            )
        """)


def list_tasks() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM scheduled_tasks ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_task(tid: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM scheduled_tasks WHERE id=?", (tid,)).fetchone()
    return dict(r) if r else None


def add_task(name: str, action: str, cron: str,
             prompt: str = "", webhook_name: str = "",
             script_path: str = "", message: str = "") -> dict:
    tid = uuid.uuid4().hex[:8]
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute(
            "INSERT INTO scheduled_tasks (id, name, prompt, cron, action, webhook_name, script_path, message, enabled, created_at) VALUES (?,?,?,?,?,?,?,?,1,?)",
            (tid, name.strip(), prompt.strip(), cron, action,
             webhook_name.strip(), script_path.strip(), message.strip(), now),
        )
    task = get_task(tid)
    _sync_to_scheduler(task)
    return task


def update_task(tid: str, **fields) -> dict | None:
    allowed = {"name", "prompt", "cron", "action", "webhook_name", "script_path", "message", "enabled"}
    with _conn() as c:
        task = c.execute("SELECT * FROM scheduled_tasks WHERE id=?", (tid,)).fetchone()
        if not task:
            return None
        task = dict(task)
        for k, v in fields.items():
            if k in allowed:
                task[k] = v
        c.execute(
            "UPDATE scheduled_tasks SET name=?, prompt=?, cron=?, action=?, webhook_name=?, script_path=?, message=?, enabled=? WHERE id=?",
            (task["name"], task["prompt"], task["cron"], task["action"],
             task["webhook_name"], task["script_path"], task["message"],
             task["enabled"], tid),
        )
    task = get_task(tid)
    _sync_to_scheduler(task)
    return task


def delete_task(tid: str) -> bool:
    with _conn() as c:
        c.execute("DELETE FROM task_log WHERE task_id=?", (tid,))
        c.execute("DELETE FROM scheduled_tasks WHERE id=?", (tid,))
    _remove_from_scheduler(tid)
    return True


def toggle_task(tid: str) -> dict | None:
    task = get_task(tid)
    if not task:
        return None
    return update_task(tid, enabled=0 if task["enabled"] else 1)


def get_log(task_id: str = None, limit: int = 20) -> list[dict]:
    with _conn() as c:
        if task_id:
            rows = c.execute(
                "SELECT * FROM task_log WHERE task_id=? ORDER BY id DESC LIMIT ?", (task_id, limit)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM task_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def add_log(task_id: str, result: str, success: bool = True) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute(
            "INSERT INTO task_log (task_id, ran_at, result, success) VALUES (?,?,?,?)",
            (task_id, now, result[:5000], 1 if success else 0),
        )


# ── APScheduler ────────────────────────────────────────────────

def _execute_task(task_id: str):
    task = get_task(task_id)
    if not task or not task.get("enabled"):
        return
    try:
        result = ""
        if task["action"] == "message":
            result = f"🔔 Rappel : {task['message'] or task['name']}"
        elif task["action"] == "script" and task["script_path"]:
            try:
                p = subprocess.run(
                    [task["script_path"]], capture_output=True, text=True, timeout=120
                )
                result = p.stdout[:3000] or f"Code {p.returncode}"
                if p.stderr:
                    result += f"\n[stderr] {p.stderr[:1000]}"
            except Exception as e:
                result = f"Erreur script : {e}"
        elif task["action"] == "webhook" and task["webhook_name"]:
            try:
                from tools.discord_webhook import send_discord
                content = task["message"] or task["prompt"] or f"⏰ Tâche : {task['name']}"
                result = send_discord(task["webhook_name"], content)
            except Exception as e:
                result = f"Erreur webhook : {e}"
        else:
            result = f"Action '{task['action']}' exécutée"
        add_log(task_id, result, success=True)
        if task.get("enabled"):
            _notify_windows(task["name"], result[:100])
    except Exception as e:
        add_log(task_id, str(e), success=False)
        _notify_windows(task.get("name", "?"), f"Erreur : {e}"[:100])


def _notify_windows(title: str, message: str) -> None:
    try:
        from plyer import notification
        notification.notify(title=f"⏰ Agent IA — {title}", message=message, timeout=5)
    except Exception:
        try:
            import subprocess as sp
            ps = (
                f'[System.Windows.Forms.MessageBox]::Show("{message}", "Agent IA — {title}")'
            )
            sp.run(["powershell", "-NoProfile", ps], capture_output=True, timeout=5)
        except Exception:
            pass


def start_scheduler():
    global _scheduler
    with _lock:
        if _scheduler is not None:
            return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        return

    sched = BackgroundScheduler(daemon=True)

    tasks = list_tasks()
    for t in tasks:
        if not t.get("enabled"):
            continue
        try:
            trigger = CronTrigger.from_crontab(t["cron"])
            sched.add_job(
                _execute_task,
                trigger=trigger,
                args=[t["id"]],
                id=f"task_{t['id']}",
                replace_existing=True,
                misfire_grace_time=300,
            )
        except Exception:
            pass

    sched.start()
    with _lock:
        _scheduler = sched


def stop_scheduler():
    global _scheduler
    with _lock:
        if _scheduler:
            _scheduler.shutdown(wait=False)
            _scheduler = None


def _sync_to_scheduler(task: dict):
    global _scheduler
    with _lock:
        s = _scheduler
    if s is None or not task.get("enabled"):
        return
    try:
        from apscheduler.triggers.cron import CronTrigger
        trigger = CronTrigger.from_crontab(task["cron"])
        s.add_job(
            _execute_task,
            trigger=trigger,
            args=[task["id"]],
            id=f"task_{task['id']}",
            replace_existing=True,
            misfire_grace_time=300,
        )
    except Exception:
        pass


def _remove_from_scheduler(tid: str):
    global _scheduler
    with _lock:
        s = _scheduler
    if s is None:
        return
    try:
        s.remove_job(f"task_{tid}")
    except Exception:
        pass


def next_run(tid: str) -> str:
    global _scheduler
    with _lock:
        s = _scheduler
    if s is None:
        return ""
    try:
        job = s.get_job(f"task_{tid}")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%d/%m %H:%M")
    except Exception:
        pass
    return ""


init_db()
