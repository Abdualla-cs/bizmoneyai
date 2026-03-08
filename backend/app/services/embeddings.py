from functools import lru_cache

import numpy as np


@lru_cache(maxsize=1)
def _get_model():
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


def embed_texts(texts: list[str]) -> np.ndarray:
    model = _get_model()
    if model is not None:
        vectors = model.encode(texts, convert_to_numpy=True)
        return vectors

    # Fallback stub when model is unavailable in local/dev environments.
    vecs = []
    for text in texts:
        seed = sum(ord(ch) for ch in text)
        rng = np.random.default_rng(seed)
        vecs.append(rng.normal(size=(384,)))
    return np.vstack(vecs)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
