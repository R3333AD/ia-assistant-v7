"""
Mémoire à long terme avec ChromaDB + chunking intelligent (RecursiveCharacterTextSplitter).
"""
import os
import hashlib
from datetime import datetime

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

try:
    import chromadb
    from chromadb.utils import embedding_functions
    _client = chromadb.PersistentClient(path=CHROMA_PATH)
    _ef = embedding_functions.DefaultEmbeddingFunction()
    _collection = _client.get_or_create_collection(name="agent_memory", embedding_function=_ef)
    CHROMA_AVAILABLE = True
except Exception:
    CHROMA_AVAILABLE = False
    _collection = None


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Découpe un texte long en morceaux avec chevauchement."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def save_memory(user_msg: str, agent_response: str):
    if not CHROMA_AVAILABLE or not _collection:
        return
    try:
        full_text = f"User: {user_msg}\nAgent: {agent_response}"
        chunks = _chunk_text(full_text)
        timestamp = datetime.now().isoformat()
        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(f"{chunk}{timestamp}{i}".encode()).hexdigest()
            _collection.add(
                documents=[chunk],
                ids=[doc_id],
                metadatas=[{"timestamp": timestamp, "chunk": i}],
            )
    except Exception:
        pass


def index_document(text: str, source: str = "document"):
    """Indexe un document (PDF, CSV...) dans ChromaDB avec chunking."""
    if not CHROMA_AVAILABLE or not _collection:
        return 0
    chunks = _chunk_text(text)
    timestamp = datetime.now().isoformat()
    indexed = 0
    for i, chunk in enumerate(chunks):
        try:
            doc_id = hashlib.md5(f"{source}{chunk}{i}".encode()).hexdigest()
            _collection.add(
                documents=[chunk],
                ids=[doc_id],
                metadatas=[{"timestamp": timestamp, "source": source, "chunk": i}],
            )
            indexed += 1
        except Exception:
            pass
    return indexed


def search_memory(query: str, n_results: int = 3) -> str:
    if not CHROMA_AVAILABLE or not _collection:
        return ""
    try:
        count = _collection.count()
        if count == 0:
            return ""
        results = _collection.query(query_texts=[query], n_results=min(n_results, count))
        docs = results.get("documents", [[]])[0]
        return ("Mémoire des sessions précédentes :\n" + "\n---\n".join(docs)) if docs else ""
    except Exception:
        return ""


def get_memory_count() -> int:
    if not CHROMA_AVAILABLE or not _collection:
        return 0
    try:
        return _collection.count()
    except Exception:
        return 0


def clear_memory():
    if not CHROMA_AVAILABLE or not _collection:
        return
    try:
        ids = _collection.get()["ids"]
        if ids:
            _collection.delete(ids=ids)
    except Exception:
        pass
