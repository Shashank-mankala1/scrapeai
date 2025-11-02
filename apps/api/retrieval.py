# apps/api/retrieval.py
from __future__ import annotations
from typing import List, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

def _make_vectorizer(n_docs: int) -> TfidfVectorizer:
    """
    Choose safe TF-IDF params based on corpus size.
    For a single document, max_df must be 1.0 to avoid
    'max_df corresponds to < documents than min_df'.
    """
    common = dict(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),  # helps with short headlines
        min_df=1,
        norm="l2",
        use_idf=True,
    )
    if n_docs <= 1:
        return TfidfVectorizer(max_df=1.0, **common)
    else:
        return TfidfVectorizer(max_df=0.9, **common)

def _clean_inputs(texts: List[str]) -> Tuple[List[str], List[int]]:
    """
    Drop empty/whitespace-only strings but keep an index map
    back to the original chunk indices.
    """
    cleaned, idxmap = [], []
    for i, t in enumerate(texts or []):
        if t and str(t).strip():
            cleaned.append(str(t))
            idxmap.append(i)
    return cleaned, idxmap

def build_retriever(texts: List[str]):
    """
    Returns (vectorizer, X). Caller must keep the idxmap from _clean_inputs.
    """
    cleaned, _ = _clean_inputs(texts)
    if not cleaned:
        return None, None
    V = _make_vectorizer(len(cleaned))
    X = V.fit_transform(cleaned)  # (n_docs, vocab)
    return V, X

def retrieve_top_k(doc, query: str, k: int = 3) -> List[Tuple[int, float]]:
    """
    Returns a list of (orig_chunk_index, score) pairs.
    """
    # 0) gather texts and keep index mapping
    all_texts = [c.text for c in doc.chunks]
    cleaned, idxmap = _clean_inputs(all_texts)
    if not cleaned:
        return []

    # 1) fit TF-IDF on cleaned texts
    V = _make_vectorizer(len(cleaned))
    X = V.fit_transform(cleaned)

    # 2) transform query and compute cosine sims (L2-normalized vectors)
    q = V.transform([query or ""])
    sims = (X @ q.T).toarray().ravel()

    # 3) graceful fallback if all zeros (no overlap on headline-style pages)
    if sims.size == 0 or float(np.max(sims)) == 0.0:
        order = np.argsort([-len(all_texts[i]) for i in idxmap])[: max(1, k)]
        return [(idxmap[int(i)], 0.0) for i in order]

    # 4) normal top-k by similarity
    order = np.argsort(-sims)[: max(1, k)]
    return [(idxmap[int(i)], float(sims[int(i)])) for i in order]
