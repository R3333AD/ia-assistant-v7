import os
import urllib.request
import urllib.parse
import json

def get_news(topic: str) -> str:
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        return f"[DÉMO] Actualités simulées pour '{topic}'. Ajoute NEWS_API_KEY dans .env (gratuit sur newsapi.org)"
    try:
        q = urllib.parse.quote(topic)
        url = f"https://newsapi.org/v2/everything?q={q}&language=fr&pageSize=3&sortBy=publishedAt&apiKey={api_key}"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        articles = data.get("articles", [])
        if not articles:
            return "Aucune actualité trouvée."
        results = []
        for a in articles:
            results.append(f"- {a['title']}\n  {a.get('description','')[:200]}\n  Source: {a['source']['name']}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Erreur news : {e}"

NEWS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_news",
        "description": "Récupère les dernières actualités sur un sujet.",
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "Sujet de recherche"}},
            "required": ["topic"],
        },
    },
}
