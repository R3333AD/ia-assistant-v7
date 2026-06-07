import os

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")

def analyze_file(filename: str, question: str = "") -> str:
    path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(path):
        return f"Fichier '{filename}' introuvable."

    ext = filename.lower().split(".")[-1]

    if ext == "csv":
        try:
            import pandas as pd
            df = pd.read_csv(path)
            summary = f"CSV : {len(df)} lignes, {len(df.columns)} colonnes.\nColonnes : {', '.join(df.columns)}\n\nAperçu :\n{df.head(5).to_string()}"
            if question:
                summary += f"\n\nQuestion : {question}\n(Analyse les données pour répondre)"
            return summary
        except Exception as e:
            return f"Erreur CSV : {e}"

    elif ext == "pdf":
        try:
            import PyPDF2
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages[:5]:  # Max 5 pages
                    text += page.extract_text() or ""
            if not text.strip():
                return "PDF vide ou non lisible."
            preview = text[:3000]
            return f"PDF ({len(reader.pages)} pages). Contenu (extrait) :\n{preview}"
        except Exception as e:
            return f"Erreur PDF : {e}"

    elif ext in ("txt", "md"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(3000)
        return f"Fichier texte :\n{content}"

    else:
        return f"Format '{ext}' non supporté. Formats acceptés : PDF, CSV, TXT, MD"

FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "analyze_file",
        "description": "Lit et analyse un fichier uploadé (PDF, CSV, TXT). Retourne son contenu ou répond à une question dessus.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Nom du fichier uploadé"},
                "question": {"type": "string", "description": "Question optionnelle sur le fichier"},
            },
            "required": ["filename"],
        },
    },
}
