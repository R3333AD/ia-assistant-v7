"""
Synthèse vocale (TTS) via Microsoft Edge — gratuit, sans clé API.
Voix FR par défaut : fr-FR-HenriNeural (homme, claire).
"""
import asyncio
import io
import re

import edge_tts

DEFAULT_VOICE = "fr-FR-HenriNeural"
MAX_CHARS = 5000


def _clean_for_tts(text: str) -> str:
    """Nettoie le markdown pour une lecture vocale fluide."""
    text = re.sub(r"```[\s\S]*?```", " bloc de code ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[•●▪►→]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def _synthesize(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice=voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def speak(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Retourne les octets MP3. À utiliser avec st.audio(bytes, autoplay=True)."""
    clean = _clean_for_tts(text)
    if not clean:
        return b""
    if len(clean) > MAX_CHARS:
        clean = clean[:MAX_CHARS] + "..."
    try:
        return asyncio.run(_synthesize(clean, voice))
    except Exception as e:
        return f"[TTS erreur : {e}]".encode("utf-8")


VOICES_FR = [
    "fr-FR-HenriNeural",
    "fr-FR-DeniseNeural",
    "fr-FR-EloiseNeural",
    "fr-FR-JacquelineNeural",
]
