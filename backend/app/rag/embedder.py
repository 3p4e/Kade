"""Sentence-transformers embedder, lazily loaded."""
from __future__ import annotations

import logging
import threading
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None


def _load():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                settings = get_settings()
                logger.info("Loading embedding model %s", settings.embedding_model)
                _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_one(text: str) -> list[float]:
    m = _load()
    vec = m.encode([text], normalize_embeddings=True)[0]
    return vec.tolist()


def embed_many(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    m = _load()
    vecs = m.encode(texts, normalize_embeddings=True, batch_size=16)
    return [v.tolist() for v in vecs]


@lru_cache(maxsize=512)
def embed_cached(text: str) -> tuple[float, ...]:
    return tuple(embed_one(text))
