"""LLM answer synthesis (Anthropic Claude). Falls back to extractive answer."""
from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a QC compliance assistant for Certificates of Analysis (CoAs). "
    "Answer the user's question strictly using the provided CoA excerpts. "
    "Cite supporting passages by their bracketed source ID like [1], [2]. "
    "If the answer is not in the excerpts, say you don't have enough information. "
    "Be concise and precise — units, batch numbers, and pass/fail status matter."
)


def _format_context(chunks: list[dict]) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, start=1):
        meta = []
        if c.get("doc_code"):
            meta.append(f"doc {c['doc_code']}")
        if c.get("batch_number"):
            meta.append(f"batch {c['batch_number']}")
        if c.get("page"):
            meta.append(f"page {c['page']}")
        header = f"[{i}] " + (", ".join(meta) if meta else f"chunk {c['chunk_id']}")
        parts.append(f"{header}\n{c['content']}")
    return "\n\n---\n\n".join(parts)


def _extractive_fallback(question: str, chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant CoA passages found for that question."
    top = chunks[0]
    return (
        f"Based on the closest CoA passage [1] (doc {top.get('doc_code') or '?'}, "
        f"batch {top.get('batch_number') or '?'}):\n\n{top['content'][:600]}"
    )


def synthesize(question: str, chunks: list[dict]) -> str:
    settings = get_settings()
    if not chunks:
        return "No relevant CoA passages were found in the knowledge base."

    if settings.llm_provider != "anthropic" or not settings.anthropic_api_key:
        return _extractive_fallback(question, chunks)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        context = _format_context(chunks)
        msg = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\nCoA excerpts:\n{context}\n\n"
                        "Answer with citations like [1], [2]."
                    ),
                }
            ],
        )
        return "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        ) or _extractive_fallback(question, chunks)
    except Exception:
        logger.exception("LLM call failed; falling back to extractive answer")
        return _extractive_fallback(question, chunks)
