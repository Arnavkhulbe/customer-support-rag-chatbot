"""Singleton holder for the local embedding model.

`all-MiniLM-L6-v2` runs fully locally and is free. The model is loaded ONCE
per process and shared by ingestion and query-time retrieval.
"""

import logging
import threading
from typing import List

from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()
_model_name: str | None = None


def get_embedding_model() -> SentenceTransformer:
    """Load the embedding model once and reuse it for every call."""
    global _model, _model_name
    if _model is not None and _model_name == settings.embedding_model:
        return _model

    with _lock:
        if _model is None or _model_name != settings.embedding_model:
            logger.info("Loading embedding model '%s' (one-time)...", settings.embedding_model)
            _model = SentenceTransformer(settings.embedding_model)
            _model_name = settings.embedding_model
            # sentence-transformers renamed this getter; support both versions.
            dim_getter = getattr(_model, "get_embedding_dimension", None) or (
                _model.get_sentence_embedding_dimension
            )
            logger.info("Embedding model loaded (dimension=%d)", dim_getter())
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts with the local model."""
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True,  # cosine-friendly unit vectors
    )
    return [emb.tolist() for emb in embeddings]


def embed_query(text: str) -> List[float]:
    """Embed a single user query."""
    return embed_texts([text])[0]
