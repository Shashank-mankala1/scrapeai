# apps/api/llm_groq.py
# Minimal Groq helper for /ask (LLM mode).
# Usage:
#   from llm_groq import answer_with_groq
#   txt = answer_with_groq(passages, question, model, api_key)

from typing import List
from groq import Groq
import httpx

_SYSTEM = (
    "You are a careful assistant for question-answering over a given document. "
    "Answer clearly using only the provided text."
    "Always return complete sentences. Do not fabricate information. "
    "Use ONLY the provided passages. If the passages are insufficient, say so clearly. "
    "Always include citations like [#i] that refer to the numbered chunks provided in the prompt. "
    "Be concise and avoid speculation."
    "Do not invent citations or refer to information not in the passages."
)

def _build_messages(passages: List[str], question: str) -> list[dict]:
    # Number the retrieved chunks 1..N for clean [#i] citations.
    ctx_lines = []
    for i, p in enumerate(passages, start=1):
        # Keep a little header so the model can refer to [#i]
        ctx_lines.append(f"[Chunk #{i}]\n{p.strip()}\n")
    user_prompt = (
        "Answer the question strictly from the chunks above.\n"
        "Include citations like [#i] matching the chunk numbers you used.\n\n"
        f"Question: {question.strip()}"
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "\n".join(ctx_lines) + "\n" + user_prompt},
    ]

def answer_with_groq(passages: List[str], question: str, model: str, api_key: str, max_tokens: int | None) -> str:
    """
    passages: list of top-k chunk texts (already trimmed by caller if desired)
    question: user question string
    model: e.g., 'llama-3.1-8b-instruct'
    api_key: your GROQ_API_KEY
    """
    print(f"Calling Groq model={model} with {len(passages)} passages...")
    if not passages:
        return "I don’t have enough context to answer from the document."

    client = Groq(api_key=api_key, timeout=httpx.Timeout(10.0, read=20.0))
    messages = _build_messages(passages, question)

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,   # keep it factual/stable
        max_tokens=7000,    # generous but safe
    )
    return (resp.choices[0].message.content or "").strip()
