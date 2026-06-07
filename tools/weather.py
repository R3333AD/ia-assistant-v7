import os
import urllib.request
import json

def get_weather(city: str) -> str:
    api_key = os.getenv("WEATHER_API_KEY", "")
    if not api_key:
        return f"[DÉMO] Météo simulée pour {city} : 22°C, ensoleillé. Ajoute WEATHER_API_KEY dans .env (gratuit sur openweathermap.org)"
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=fr"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        return f"Météo à {city} : {temp}°C (ressenti {feels}°C), {desc}, humidité {humidity}%"
    except Exception as e:
        return f"Erreur météo : {e}"

WEATHER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Donne la météo actuelle d'une ville.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "Nom de la ville"}},
            "required": ["city"],
        },
    },
}
