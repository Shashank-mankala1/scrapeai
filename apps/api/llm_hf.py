from __future__ import annotations
import os, requests
from typing import List

HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "google/gemma-2-2b-it")
HF_URL = f"https://api-inference.huggingface.co/models/microsoft/Phi-3-mini-4k-instruct"

def _build_prompt(question: str, snippets: List[str]) -> str:
    blocks = "\n\n".join(f"[#{i+1}] {s}" for i, s in enumerate(snippets))
    return (
        "You are a careful assistant. Answer ONLY using the provided passages.\n"
        "If the answer is not present, say you cannot find it. "
        "Cite supporting passages inline like [#1], [#2]. Be concise and factual.\n\n"
        f"Passages:\n{blocks}\n\nQuestion: {question}\n"
        "Answer:"
    )

def answer_with_hf(question: str, snippets: List[str], max_new_tokens: int = 200, temperature: float = 0.2) -> str:
    print(HF_TOKEN)
    if not HF_TOKEN:
        return "❌ Missing HF_TOKEN; falling back to extractive mode."
    prompt = _build_prompt(question, snippets)
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "return_full_text": False
        }
    }
    try:
        r = requests.post(HF_URL, headers=headers, json=payload, timeout=120)
        # Cold starts or queued models may return 503 with a message
        if r.status_code == 503:
            return "⏳ Model warming up on Hugging Face (503). Try again in a moment, or use extractive mode."
        r.raise_for_status()
        data = r.json()
        # Most text-generation models return a list with {'generated_text': ...}
        if isinstance(data, list) and data and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()
        # Some endpoints return dict with 'generated_text'
        if isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"].strip()
        # Fallback: stringify
        return str(data)
    except Exception as e:
        return f"❌ HF error: {e}"
