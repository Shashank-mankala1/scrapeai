import hashlib
import httpx
import trafilatura
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # deterministic

DEFAULT_HEADERS = {
    "User-Agent": "AIScrapeBot/0.1 (+https://example.com) Python-httpx"
}

async def fetch_html(url: str, timeout_s: int = 15) -> str:
    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=timeout_s) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

def extract_main(url: str, html: str):
    downloaded = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        with_metadata=True,
        url=url,
    )
    if not downloaded:
        return {"title": None, "text": None}
    meta = trafilatura.metadata.extract_metadata(downloaded)
    title = meta.title if meta else None
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False, with_metadata=False)
    return {"title": title, "text": text}

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

def guess_lang(text: str) -> str | None:
    try:
        return detect(text)
    except Exception:
        return None
