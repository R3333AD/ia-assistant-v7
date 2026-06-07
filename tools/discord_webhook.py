import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError

WEBHOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "discord_webhooks.json")


def _load_webhooks() -> dict:
    if not os.path.exists(WEBHOOKS_PATH):
        return {}
    try:
        with open(WEBHOOKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_webhooks(data: dict) -> None:
    os.makedirs(os.path.dirname(WEBHOOKS_PATH), exist_ok=True)
    with open(WEBHOOKS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_webhooks() -> list[dict]:
    data = _load_webhooks()
    return [{"name": k, "url": v[:50] + "..."} for k, v in data.items()]


def save_webhook(name: str, url: str) -> None:
    data = _load_webhooks()
    data[name.strip()] = url.strip()
    _save_webhooks(data)


def delete_webhook(name: str) -> None:
    data = _load_webhooks()
    data.pop(name, None)
    _save_webhooks(data)


def send_webhook(url: str, content: str, username: str = "Agent IA") -> str:
    payload = json.dumps({"content": content[:2000], "username": username}).encode("utf-8")
    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=10) as resp:
            return f"✅ Message envoyé à Discord (status {resp.status})"
    except URLError as e:
        return f"Erreur Discord : {e.reason.decode() if isinstance(e.reason, bytes) else e.reason}"
    except Exception as e:
        return f"Erreur Discord : {e}"


def send_discord(name_or_url: str, content: str) -> str:
    """
    Envoie un message sur Discord.
    Si name_or_url correspond à une webhook enregistrée, utilise son URL.
    Sinon, traite comme une URL de webhook directe.
    """
    webhooks = _load_webhooks()
    url = webhooks.get(name_or_url.strip())
    if url:
        return send_webhook(url, content)
    if name_or_url.startswith("http"):
        return send_webhook(name_or_url.strip(), content)
    return f"Webhook '{name_or_url}' introuvable. Webhooks enregistrées : {', '.join(webhooks.keys()) or 'aucune'}."


DISCORD_SCHEMA = {
    "type": "function",
    "function": {
        "name": "send_discord",
        "description": "Envoie un message sur un webhook Discord. Utilise un nom de webhook enregistré ou une URL complète.",
        "parameters": {
            "type": "object",
            "properties": {
                "name_or_url": {
                    "type": "string",
                    "description": "Nom de la webhook enregistrée (ex: 'Serveur FiveM') ou URL complète du webhook Discord",
                },
                "content": {
                    "type": "string",
                    "description": "Contenu du message (max 2000 caractères)",
                },
            },
            "required": ["name_or_url", "content"],
        },
    },
}
