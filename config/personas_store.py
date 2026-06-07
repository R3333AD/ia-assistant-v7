import json, os

_PERSONAS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "custom_personas.json")


def _load_all():
    if not os.path.exists(_PERSONAS_PATH):
        return {}
    try:
        with open(_PERSONAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_all(data: dict):
    os.makedirs(os.path.dirname(_PERSONAS_PATH), exist_ok=True)
    with open(_PERSONAS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def list_personas() -> dict:
    return _load_all()


def save_persona(name: str, prompt: str):
    data = _load_all()
    data[name] = prompt
    _save_all(data)


def delete_persona(name: str) -> bool:
    data = _load_all()
    if name in data:
        del data[name]
        _save_all(data)
        return True
    return False
