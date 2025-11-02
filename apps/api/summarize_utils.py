from typing import List, Dict, Any
from doc_store import Document, Chunk
import re

def _sentences(text: str) -> List[str]:
    # Simple sentence split; good enough for MVP
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text.strip())
    return [p.strip() for p in parts if p.strip()]

def summarize_document(doc: Document, style: str = "tldr") -> Dict[str, Any]:
    """
    style: 'tldr' | 'executive' | 'notes'
    Returns { title, tldr, bullets: [{text, cites:[int]}] }
    """
    bullets: List[Dict[str, Any]] = []

    # take 1–2 lead sentences per chunk
    for idx, ch in enumerate(doc.chunks, start=1):
        sents = _sentences(ch.text)
        if not sents:
            continue
        if style == "notes":
            # 2 sentences if available
            text = " ".join(sents[:2])
        elif style == "executive":
            text = sents[0]
        else:  # tldr
            text = sents[0]
        bullets.append({"text": text, "cites": [idx]})

    # TL;DR: first bullet or first 25–35 words of doc
    tldr_src = bullets[0]["text"] if bullets else doc.text[:200]
    tldr_words = tldr_src.split()
    tldr = " ".join(tldr_words[: min(len(tldr_words), 30)])  # ~30 words

    return {
        "title": doc.title,
        "tldr": tldr,
        "bullets": bullets
    }
