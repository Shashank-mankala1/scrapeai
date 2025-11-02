from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, HttpUrl
from fastapi.middleware.cors import CORSMiddleware 
from ingest_utils import fetch_html, extract_main, content_hash, guess_lang
from chunking import build_chunks
from doc_store import save_document, get_document, Document
from typing import Literal, List, Tuple
from summarize_utils import summarize_document
from doc_store import get_document
from retrieval import retrieve_top_k, build_retriever
from dotenv import load_dotenv
load_dotenv()
import re
import os
from groq_router import call_with_fallback
from groq_router import last_status

app = FastAPI(title="AI-Scrape API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ai-scrape-api-72345269003.us-central1.run.app/"
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def read_root():
    return {"message": "AI-Scrape API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


class SummarizeRequest(BaseModel):
    url: str

class SummarizeResponse(BaseModel):
    summary: str

class SummarizeByIdRequest(BaseModel):
    doc_id: str
    style: Literal["tldr", "executive", "notes"] = "tldr"

class Bullet(BaseModel):
    text: str
    cites: list[int]

class SummarizeByIdResponse(BaseModel):
    title: str | None
    tldr: str
    bullets: list[Bullet]

@app.post("/summarize", response_model=SummarizeByIdResponse)
def summarize_by_id(payload: SummarizeByIdRequest):
    doc = get_document(payload.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Unknown doc_id")
    result = summarize_document(doc, style=payload.style)
    return SummarizeByIdResponse(**result)

class AskByIdRequest(BaseModel):
    doc_id: str
    question: str
    k: int = 3
    mode: Literal["extractive", "llm"] = "llm"          # default to LLM mode
    tier: Literal["economy", "accuracy"] = "economy"    # kept for future use

class Snippet(BaseModel):
    chunk_index: int    # 1-based index for user-friendly citations
    score: float
    text: str

class AskByIdResponse(BaseModel):
    answer: str
    snippets: list[Snippet]
    cites: list[int]

SPACE_JOINS = re.compile(r"\s+")
NO_SPACE_BETWEEN_SENTENCES = re.compile(r"(?<=[a-z0-9][.!?])(?=[A-Z(])")
NO_SPACE_BEFORE_DIGIT = re.compile(r"(?<=[A-Za-z])(?=\d)")
TIMESTAMPS = re.compile(r"\b(\d+\s*(mins?|minutes?|hours?|hrs?)\s*ago)\b", re.I)

_WS = re.compile(r"\s+")
_STUCK_SENTENCES = re.compile(r"(?<=[a-z0-9][.!?])(?=[A-Z(])")   # ...endOfSent)NextStart
_STUCK_HEADLINES = re.compile(r"(?<=[a-z])(?=[A-Z])")            # wordWord -> word Word
_TIMESTAMPS = re.compile(r"\b(\d+\s*(mins?|minutes?|hours?|hrs?)\s*ago)\b", re.I)
BROKEN = re.compile(r"([a-z])\s*[\r\n]+\s*([a-z])", re.I)

_WS = re.compile(r"\s+")
_STUCK_SENTENCES = re.compile(r"(?<=[a-z0-9][.!?])(?=[A-Z(])")
_STUCK_HEADLINES = re.compile(r"(?<=[a-z])(?=[A-Z])")
_TIMESTAMPS = re.compile(r"\b(\d+\s*(mins?|minutes?|hours?|hrs?)\s*ago)\b", re.I)
# 👇 NEW: join words split by newlines, e.g. "Ukrain\nian" → "Ukrainian"
_JOIN_SPLIT_WORDS = re.compile(r"([A-Za-z])\s*[\r\n]+\s*([A-Za-z])")

_WS = re.compile(r"\s+")
_STUCK_SENTENCES = re.compile(r"(?<=[a-z0-9][.!?])(?=[A-Z(])")
_STUCK_HEADLINES = re.compile(r"(?<=[a-z])(?=[A-Z])")
_TIMESTAMPS = re.compile(r"\b(\d+\s*(mins?|minutes?|hours?|hrs?)\s*ago)\b", re.I)

# NEW: line-wrap fixes
_WRAP_HYPHEN = re.compile(r"(\w)-\s*[\r\n]+\s*(\w)")            # word-\n wrap
_WRAP_INWORD  = re.compile(r"([A-Za-z])\s*[\r\n]+\s*([a-z])")   # in-word wrap
_WRAP_PUNCT   = re.compile(r"([.,;:!?])\s*[\r\n]+\s*")          # newline after punctuation

def _clean_line(text: str) -> str:
    t = text.replace("•", " • ")

    # remove timestamps like "3 hrs ago"
    t = _TIMESTAMPS.sub("", t)

    # fix line wraps (order matters)
    t = _WRAP_HYPHEN.sub(r"\1\2", t)   # join hyphen-wrapped words
    t = _WRAP_INWORD.sub(r"\1\2", t)   # join words split by newline
    t = _WRAP_PUNCT.sub(r"\1 ", t)     # keep a space after punctuation

    # normalize spaces + typical headline glue
    t = _WS.sub(" ", t).strip()
    t = _STUCK_SENTENCES.sub(" ", t)
    t = _STUCK_HEADLINES.sub(" ", t)
    return t

def _first_sentences(text: str, max_chars: int = 300) -> str:
    t = _clean_line(text)
    parts = re.split(r"(?<=[.!?])\s+", t)
    out, total = [], 0
    for p in parts:
        if not p: continue
        if total + len(p) + 1 > max_chars: break
        out.append(p); total += len(p) + 1
        if len(out) >= 2: break
    return " ".join(out) if out else t[:max_chars]

def _postprocess_answer(ans: str) -> str:
    a = re.sub(r"\r\n?", "\n", ans or "")
    a = re.sub(r"[ \t]+", " ", a).strip()
    a = re.sub(r"^\s*\d+[\.)]\s*", "• ", a, flags=re.M)  # 1. -> •
    a = re.sub(r"\n{3,}", "\n\n", a)
    return a

class AskByIdRequest(BaseModel):
    doc_id: str
    question: str
    k: int = 3
    mode: Literal["extractive", "llm"] = "llm"
    tier: Literal["economy", "accuracy"] = "economy"

class Snippet(BaseModel):
    chunk_index: int
    score: float
    text: str

class AskByIdResponse(BaseModel):
    answer: str
    snippets: List[Snippet]
    cites: List[int]

@app.post("/ask", response_model=AskByIdResponse)
def ask_by_id(payload: AskByIdRequest):
    doc = get_document(payload.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Unknown doc_id")

    # 1) retrieve
    ranked: List[Tuple[int, float]] = retrieve_top_k(doc, payload.question, k=payload.k)

    snippets: list[Snippet] = []
    cites: list[int] = []
    top_chunks_texts: list[str] = []
    for idx, score in ranked:
        raw = doc.chunks[idx].text.strip()
        clean = _clean_line(raw)
        snippets.append(Snippet(chunk_index=idx + 1, score=float(score), text=clean))
        cites.append(idx + 1)
        top_chunks_texts.append(clean[:800])

    # 2) extractive answer (baseline & fallback)
    stitched = [_first_sentences(doc.chunks[idx].text) for idx, _ in ranked]
    extractive_answer = "\n\n".join([s for s in stitched if s]).strip() or "No relevant content found."

    # 3) choose path
    provider = os.getenv("LLM_PROVIDER", "").lower()
    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instruct")
    # print(payload.mode, provider, "Groq key present" if groq_key else "No Groq key")
    # if user asked extractive OR Groq not available → return extractive
    if payload.mode == "extractive" or provider != "groq" or not groq_key:
        return AskByIdResponse(answer=extractive_answer, snippets=snippets, cites=cites)

    # 4) try Groq; on error, fall back silently to extractive
    try:
        llm_ans, used_model = call_with_fallback(top_chunks_texts, payload.question, groq_key)
        if llm_ans is None:
            # All models failed or were rate-limited → graceful degrade
            print("All Groq models failed or were rate-limited.")
            return AskByIdResponse(answer=extractive_answer, snippets=snippets, cites=cites)
        return AskByIdResponse(answer=llm_ans, snippets=snippets, cites=cites)
    except Exception as e:
        # log for yourself; user still gets a good answer
        print("Groq error -> falling back:", repr(e))
        return AskByIdResponse(answer=extractive_answer, snippets=snippets, cites=cites)



def window_around(text: str, max_chars: int = 700) -> str:
    if len(text) <= max_chars:
        return text
    # prefer first 2–3 sentences
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    out = []
    for s in sentences:
        if sum(len(x) for x in out) + len(s) > max_chars:
            break
        out.append(s)
    return " ".join(out).strip()

class IngestRequest(BaseModel):
    url: HttpUrl

class IngestResponse(BaseModel):
    doc_id: str
    title: str | None
    lang: str | None
    word_count: int
    chunks: int
    hash: str
class DOMIngestRequest(BaseModel):
    url: HttpUrl
    html: str

@app.post("/ingest", response_model=IngestResponse)
async def ingest(payload: IngestRequest):
    try:
        html = await fetch_html(str(payload.url))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")

    extracted = extract_main(str(payload.url), html)
    text = (extracted.get("text") or "").strip()
    title = extracted.get("title") or str(payload.url).split("/")[-1]

    if not text:
        raise HTTPException(status_code=422, detail="Could not extract main content")

    return _create_doc_from_text(url=str(payload.url), title=title, text=text)
    # lang = guess_lang(text[:5000])
    # wc = len(text.split())
    # h = content_hash(text)
    # chunks = build_chunks(text, target_size=1200)

    # doc_id = save_document(
    #     url=str(payload.url),
    #     title=title,
    #     lang=lang,
    #     text=text,
    #     hash_=h,
    #     chunks=chunks
    # )

    # return IngestResponse(
    #     doc_id=doc_id,
    #     title=title,
    #     lang=lang,
    #     word_count=wc,
    #     chunks=len(chunks),
    #     hash=h
    # )

@app.post("/ingest_dom", response_model=IngestResponse)
async def ingest_dom(payload: DOMIngestRequest):
    # Reuse the same extraction + doc creation path as /ingest
    extracted = extract_main(str(payload.url), payload.html)
    text = (extracted.get("text") or "").strip()
    title = extracted.get("title") or str(payload.url).split("/")[-1]

    if not text:
        raise HTTPException(status_code=422, detail="Could not extract main content from DOM")

    # same as /ingest
    return _create_doc_from_text(url=str(payload.url), title=title, text=text)
    # lang = guess_lang(text[:5000])
    # h = content_hash(text)
    # chunks = build_chunks(text, target_size=1200, overlap=200)

    # doc_id = save_document(
    #     url=str(payload.url),
    #     title=title,
    #     lang=lang,
    #     text=text,
    #     hash_=h,
    #     chunks=chunks
    # )

    # return IngestResponse(
    #     doc_id=doc_id,
    #     title=title,
    #     lang=lang,
    #     word_count=len(text.split()),
    #     chunks=len(chunks),
    #     hash=h,
    # )


def _create_doc_from_text(url: str, title: str, text: str) -> IngestResponse:
    lang = guess_lang(text[:5000])
    h = content_hash(text)
    chunks = build_chunks(text, target_size=1200)
    doc_id = save_document(url=url, title=title, lang=lang, text=text, hash_=h, chunks=chunks)
    return IngestResponse(
        doc_id=doc_id, title=title, lang=lang,
        word_count=len(text.split()), chunks=len(chunks), hash=h
    )


class DocInfo(BaseModel):
    doc_id: str
    url: str
    title: str | None
    lang: str | None
    word_count: int
    chunks: int
    hash: str
    preview: str

@app.get("/doc/{doc_id}", response_model=DocInfo)
def get_doc(doc_id: str = Path(...)):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Unknown doc_id")
    return DocInfo(
        doc_id=doc.id,
        url=doc.url,
        title=doc.title,
        lang=doc.lang,
        word_count=len(doc.text.split()),
        chunks=len(doc.chunks),
        hash=doc.hash,
        preview=doc.text[:400]
    )
@app.get("/health")
async def health():
    return {"ok": True, "provider": os.getenv("LLM_PROVIDER"), "models": os.getenv("GROQ_MODELS")}

@app.get("/health/groq")
async def groq_health():
    """
    Returns the last successful model used and environment status.
    Example: {"last_model":"llama-3.1-70b-versatile", "last_time":"2025-11-01T14:32Z", "models":["..."], "api_key_loaded":true}
    """
    return last_status()

