"""
Base de données projets (Nova Optimizer, PC-Checker, etc.).
Stockage JSON, simple, robuste, lisible et éditable à la main.
"""
import json
import os
import uuid
from datetime import datetime

PROJECTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "projects.json")

VALID_STATUS = ("en cours", "en pause", "terminé", "abandonné", "planifié")


def _load() -> list[dict]:
    if not os.path.exists(PROJECTS_PATH):
        return []
    try:
        with open(PROJECTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(projects: list[dict]) -> None:
    os.makedirs(os.path.dirname(PROJECTS_PATH), exist_ok=True)
    with open(PROJECTS_PATH, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)


def list_projects() -> list[dict]:
    return _load()


def get_project(pid: str) -> dict | None:
    for p in _load():
        if p["id"] == pid:
            return p
    return None


def find_by_name(name: str) -> dict | None:
    n = name.lower().strip()
    for p in _load():
        if p["name"].lower() == n:
            return p
    return None


def create_project(name: str, description: str = "", status: str = "planifié", tags: list[str] = None) -> dict:
    projects = _load()
    now = datetime.now().isoformat(timespec="seconds")
    p = {
        "id": uuid.uuid4().hex[:8],
        "name": name.strip(),
        "status": status if status in VALID_STATUS else "planifié",
        "description": description.strip(),
        "tags": tags or [],
        "todos": [],
        "created_at": now,
        "updated_at": now,
    }
    projects.append(p)
    _save(projects)
    return p


def update_project(pid: str, **fields) -> dict | None:
    projects = _load()
    for p in projects:
        if p["id"] == pid:
            for k, v in fields.items():
                if k == "status" and v not in VALID_STATUS:
                    continue
                if k in p and k not in ("id", "created_at"):
                    p[k] = v
            p["updated_at"] = datetime.now().isoformat(timespec="seconds")
            _save(projects)
            return p
    return None


def delete_project(pid: str) -> bool:
    projects = _load()
    new = [p for p in projects if p["id"] != pid]
    if len(new) == len(projects):
        return False
    _save(new)
    return True


def add_todo(pid: str, text: str) -> dict | None:
    projects = _load()
    for p in projects:
        if p["id"] == pid:
            p["todos"].append({
                "id": uuid.uuid4().hex[:6],
                "text": text.strip(),
                "done": False,
            })
            p["updated_at"] = datetime.now().isoformat(timespec="seconds")
            _save(projects)
            return p
    return None


def toggle_todo(pid: str, todo_id: str) -> dict | None:
    projects = _load()
    for p in projects:
        if p["id"] == pid:
            for t in p["todos"]:
                if t["id"] == todo_id:
                    t["done"] = not t["done"]
                    p["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    _save(projects)
                    return p
    return None


def remove_todo(pid: str, todo_id: str) -> dict | None:
    projects = _load()
    for p in projects:
        if p["id"] == pid:
            p["todos"] = [t for t in p["todos"] if t["id"] != todo_id]
            p["updated_at"] = datetime.now().isoformat(timespec="seconds")
            _save(projects)
            return p
    return None


def projects_to_context() -> str:
    """Résumé compact pour injection dans le prompt système."""
    projects = _load()
    if not projects:
        return ""
    lines = ["Projets en cours de l'utilisateur :"]
    for p in projects:
        status = p.get("status", "?")
        name = p.get("name", "?")
        desc = p.get("description", "")
        todos = p.get("todos", [])
        open_todos = [t["text"] for t in todos if not t.get("done")]
        line = f"- [{status}] {name}"
        if desc:
            line += f" — {desc}"
        if open_todos:
            line += f" (TODO : {', '.join(open_todos[:5])})"
        lines.append(line)
    return "\n".join(lines)
