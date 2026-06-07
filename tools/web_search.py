import os

try:
    from tavily import TavilyClient
    _key = os.getenv("TAVILY_API_KEY", "")
    _client = TavilyClient(api_key=_key) if _key else None
except ImportError:
    _client = None

def web_search(query: str) -> str:
    if _client:
        try:
            response = _client.search(query, max_results=3)
            results = response.get("results", [])
            return "\n\n".join([f"- {r['title']}\n  {r.get('content','')[:300]}" for r in results]) or "Aucun résultat."
        except Exception as e:
            return f"Erreur : {e}"
    return f"[DÉMO] Pas de clé Tavily pour : '{query}'. Ajoute TAVILY_API_KEY dans .env"

WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Recherche des informations récentes sur le web.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "La requête"}},
            "required": ["query"],
        },
    },
}
