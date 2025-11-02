from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional
from uuid import uuid4
from datetime import datetime

@dataclass
class Chunk:
    id: str
    start: int
    end: int
    text: str

@dataclass
class Document:
    id: str
    url: str
    title: Optional[str]
    lang: Optional[str]
    text: str
    chunks: List[Chunk]
    hash: str
    created_at: datetime

_DB: Dict[str, Document] = {}

def save_document(url: str, title: Optional[str], lang: Optional[str], text: str, hash_: str, chunks: List[Chunk]) -> str:
    doc_id = str(uuid4())
    _DB[doc_id] = Document(
        id=doc_id, url=url, title=title, lang=lang, text=text,
        chunks=chunks, hash=hash_, created_at=datetime.utcnow()
    )
    return doc_id

def get_document(doc_id: str) -> Optional[Document]:
    return _DB.get(doc_id)

def count() -> int:
    return len(_DB)
