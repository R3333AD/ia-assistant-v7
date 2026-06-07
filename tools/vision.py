"""
Outil Vision — analyse d'images avec Llama 4 Scout (modèle multimodal Groq).
"""
import os
import base64
from groq import Groq
from config.settings import GROQ_API_KEY

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def analyze_image(image_path: str, question: str = "Décris cette image en détail.") -> str:
    """
    Analyse une image et répond à une question dessus.
    image_path : chemin local vers l'image (jpg, png, webp)
    question   : ce qu'on veut savoir sur l'image
    """
    if not os.path.exists(image_path):
        return f"Image introuvable : {image_path}"

    ext = image_path.lower().split(".")[-1]
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "gif": "image/gif"}
    mime = mime_map.get(ext, "image/jpeg")

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": question},
                ],
            }],
            max_tokens=1024,
        )
        return response.choices[0].message.content or "Pas de réponse."
    except Exception as e:
        return f"Erreur vision : {e}"


VISION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "analyze_image",
        "description": (
            "Analyse une image uploadée et répond à une question dessus. "
            "Peut décrire, lire du texte (OCR), identifier des objets, analyser des graphiques, des screenshots..."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Chemin vers l'image uploadée"},
                "question":   {"type": "string", "description": "Question sur l'image (optionnel)"},
            },
            "required": ["image_path"],
        },
    },
}
