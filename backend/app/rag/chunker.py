"""Simple recursive text chunker with overlap."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    index: int
    page: int | None
    content: str


def chunk_text(text: str, page: int | None = None, *, size: int = 900, overlap: int = 150) -> list[Chunk]:
    text = text.strip()
    if not text:
        return []
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        # Snap to nearest sentence/paragraph boundary if possible
        if end < n:
            window = text[start:end]
            for sep in ("\n\n", ". ", "\n", " "):
                pos = window.rfind(sep)
                if pos > size * 0.6:
                    end = start + pos + len(sep)
                    break
        chunks.append(Chunk(index=idx, page=page, content=text[start:end].strip()))
        idx += 1
        if end >= n:
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c.content]


def chunk_pages(pages: list[tuple[int, str]], *, size: int = 900, overlap: int = 150) -> list[Chunk]:
    out: list[Chunk] = []
    for page_no, text in pages:
        for c in chunk_text(text, page=page_no, size=size, overlap=overlap):
            c.index = len(out)
            out.append(c)
    return out
