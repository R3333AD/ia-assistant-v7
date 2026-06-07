import json
import os

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "profile.json")

DEFAULT_PROFILE = {
    "name": "",
    "job": "",
    "interests": "",
    "language": "français",
    "notes": ""
}


def load_profile() -> dict:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_PROFILE.copy()


def save_profile(profile: dict):
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def profile_to_context(profile: dict) -> str:
    parts = []
    if profile.get("name"):
        parts.append(f"- Prénom de l'utilisateur : {profile['name']}")
    if profile.get("job"):
        parts.append(f"- Métier : {profile['job']}")
    if profile.get("interests"):
        parts.append(f"- Centres d'intérêt : {profile['interests']}")
    if profile.get("notes"):
        parts.append(f"- Notes personnelles : {profile['notes']}")
    if not parts:
        return ""
    return "Informations sur l'utilisateur :\n" + "\n".join(parts)
