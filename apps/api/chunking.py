import re
from typing import List, Tuple
from doc_store import Chunk
from uuid import uuid4

_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9])')

# apps/api/chunking.py
import re

CHUNK_SIZE = 1400    # you can tune this up or down
OVERLAP = 150        # overlap between consecutive chunks

def snap_end_to_sentence(text: str, limit: int) -> str:
    """Trim text to nearest sentence end within `limit` characters."""
    if len(text) <= limit:
        return text

    # take up to limit, then backtrack to the last sentence end
    window = text[:limit]
    # look backwards for a sentence boundary
    m = re.search(r"[\.!?](?:\"|')?\s+[A-Z(]", window[::-1])
    if m:
        cut = limit - m.start()
        return text[:cut].rstrip()

    # fallback: avoid cutting mid-word
    m2 = re.search(r"\s+\S+$", window)
    return window[:m2.start()].rstrip() if m2 else window.rstrip()


def make_chunks(full_text: str):
    """Split the full text into overlapping chunks that end cleanly on sentences."""
    chunks = []
    i = 0
    while i < len(full_text):
        piece = full_text[i:i + CHUNK_SIZE + 200]  # take a bit extra headroom
        piece = snap_end_to_sentence(piece, CHUNK_SIZE)
        chunks.append(piece)
        i += max(1, len(piece) - OVERLAP)
    return chunks


def split_into_sentences(text: str) -> List[str]:
    # crude but good enough for MVP
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]

def build_chunks(text: str, target_size: int = 1200, overlap_sentences: int = 1) -> List[Chunk]:
    """
    Pack full sentences into ~target_size-char chunks.
    Chunks start and end on sentence boundaries.
    Overlap is by N sentences (default 1), not by raw characters.
    """
    sents = split_into_sentences(text)
    if not sents:
        return [Chunk(id=str(uuid4()), start=0, end=len(text), text=text)]

    # Map each sentence to its (start,end) offsets in the original text
    indices: List[Tuple[int, int]] = []
    cursor = 0
    for s in sents:
        i = text.find(s, cursor)
        if i == -1:
            i = text.find(s)  # fallback if duplicates exist
        start, end = i, i + len(s)
        indices.append((start, end))
        cursor = end

    chunks: List[Chunk] = []
    i = 0
    while i < len(sents):
        start_idx = max(0, i - overlap_sentences) if chunks else i  # add sentence overlap after the first chunk
        start_off = indices[start_idx][0]

        # include sentences until we approach target_size
        j = i
        end_off = indices[j][1]
        while j + 1 < len(sents):
            next_end = indices[j + 1][1]
            if next_end - start_off > target_size:
                break
            j += 1
            end_off = indices[j][1]

        chunk_text = text[start_off:end_off]
        chunks.append(Chunk(id=str(uuid4()), start=start_off, end=end_off, text=chunk_text))

        # advance; keep an overlap of N sentences
        i = j + 1

    return chunks

