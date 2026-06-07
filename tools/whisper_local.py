"""
Reconnaissance vocale locale via faster-whisper (CTranslate2).
Modèle téléchargé automatiquement au premier appel (~500 Mo pour 'small').
Fonctionne hors ligne, pas de clé API nécessaire.
"""
import io
import wave
import numpy as np
import os

_MODEL = None
_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")  # tiny, small, medium, large-v3


def is_available() -> bool:
    try:
        import faster_whisper
        return True
    except ImportError:
        return False


def transcribe_local(audio_bytes: bytes, language: str = "fr") -> str:
    global _MODEL
    if not is_available():
        return ""
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
    try:
        with io.BytesIO(audio_bytes) as buf:
            with wave.open(buf, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = _MODEL.transcribe(audio, language=language)
        return " ".join(seg.text for seg in segments).strip()
    except Exception as e:
        return f"[Whisper local erreur : {e}]"
