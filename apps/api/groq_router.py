# apps/api/groq_router.py
import os
import time
from typing import List, Tuple, Optional

# Classify transient vs hard errors to decide whether to try next model.
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES_PER_MODEL = 2  # backoff per model before trying the next
BASE_BACKOFF = 0.4         # seconds

def _models() -> List[str]:
    return [m.strip() for m in os.getenv("GROQ_MODELS", "").split(",") if m.strip()]

def _max_tokens() -> int:
    try:
        return int(os.getenv("GROQ_MAX_TOKENS", "7000"))
    except Exception:
        return 7000

def call_with_fallback(passages: List[str], question: str, api_key: str):
    """
    Tries models in priority order. Retries transient failures with backoff.
    On context-length errors or persistent failure, falls through to next model.
    Returns (answer_text, model_used) or (None, None) if all failed.
    """
    from llm_groq import answer_with_groq  # local import to avoid cycles

    msgs_len = sum(len(p) for p in passages) + len(question)
    max_out = _max_tokens()
    print(f"Total input length: {msgs_len} chars; max output tokens: {max_out}")
    print("Trying Groq models:", _models())
    for model in _models():
        # per-model retry loop for transient errors
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            try:
                print("Trying model:", model)
                ans = answer_with_groq(passages, question, model, api_key, max_tokens=max_out)
                record_success(model)
                return ans, model
            except Exception as e:
                print(f"Groq model={model} attempt={attempt} error: {repr(e)}")
                # Heuristics: inspect common Groq errors if exposed
                msg = str(e).lower()

                # Treat obvious context issues as non-transient—try next model immediately
                if "context" in msg and ("length" in msg or "token" in msg):
                    break  # move to next model

                # If exception exposes HTTP status, handle transient ones with backoff
                status = _extract_status_code(msg)  # see helper below
                if status in TRANSIENT_STATUSES or "rate" in msg or "overload" in msg or "timeout" in msg:
                    if attempt < MAX_RETRIES_PER_MODEL:
                        time.sleep(BASE_BACKOFF * attempt)
                        continue
                # Non-transient or retries exhausted: go to next model
                break
    return None, None

def _extract_status_code(msg: str) -> Optional[int]:
    # naive helper to fish out 3-digit HTTP codes from error strings
    import re
    m = re.search(r"\b(4\d\d|5\d\d)\b", msg)
    return int(m.group(1)) if m else None


_last_success: dict[str, str] = {"model": None, "timestamp": None}

def record_success(model: str):
    """Called after a successful LLM completion."""
    from datetime import datetime
    _last_success["model"] = model
    _last_success["timestamp"] = datetime.utcnow().isoformat()

def last_status():
    """Expose last known success and available models."""
    return {
        "last_model": _last_success["model"],
        "last_time": _last_success["timestamp"],
        "models": [m.strip() for m in os.getenv("GROQ_MODELS", "").split(",") if m.strip()],
        "api_key_loaded": bool(os.getenv("GROQ_API_KEY")),
    }