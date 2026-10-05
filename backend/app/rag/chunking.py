"""Text chunking for RAG ingestion.

Splits extracted page text into overlapping chunks. Words are used as a proxy
for tokens — good enough for policy documents and fully deterministic.

The splitter prefers paragraph boundaries, then sentence boundaries, and only
falls back to hard word splits when a single paragraph/sentence exceeds the
chunk size. This keeps statements like
"Eligible products may be returned within 10 calendar days from the date of
delivery." inside a single chunk.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


@dataclass
class Chunk:
    text: str
    source: str
    page: int
    chunk_index: int
    document_type: str


def document_type_from_filename(filename: str) -> str:
    """'payment-refund-policy.pdf' -> 'payment_refund_policy'."""
    stem = Path(filename).stem
    return stem.replace("-", "_").replace(" ", "_").lower()


def _split_oversized(text: str, limit: int) -> List[str]:
    """Split a single paragraph/sentence that is longer than `limit` words."""
    words = text.split()
    return [" ".join(words[i : i + limit]) for i in range(0, len(words), limit)]


def _split_paragraph(paragraph: str, size: int, overlap: int) -> List[str]:
    """Split one paragraph into word-window pieces with overlap."""
    pieces: List[str] = []
    words = paragraph.split()
    step = max(size - overlap, 1)
    i = 0
    while i < len(words):
        piece = " ".join(words[i : i + size])
        if piece:
            pieces.append(piece)
        if i + size >= len(words):
            break
        i += step
    return pieces


def chunk_page_text(page_text: str, source: str, page: int) -> List[str]:
    """Chunk the text of a single page into overlapping word-window chunks."""
    size = settings.chunk_size
    overlap = settings.chunk_overlap

    if not page_text.strip():
        return []

    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(page_text) if p.strip()]
    if not paragraphs:
        return []

    # Pack whole paragraphs while they fit (paragraph = natural unit).
    packed: List[str] = []
    current: List[str] = []
    current_len = 0
    for paragraph in paragraphs:
        para_len = len(paragraph.split())
        if para_len > size:
            # Paragraph itself is too big: flush what we have, then window it.
            if current:
                packed.append(" ".join(current))
                current, current_len = [], 0
            packed.extend(_split_paragraph(paragraph, size, overlap))
            continue
        if current_len + para_len + 1 > size and current:
            packed.append(" ".join(current))
            current, current_len = [], 0
        current.append(paragraph)
        current_len += para_len
    if current:
        packed.append(" ".join(current))

    # Split any packed block that still exceeds the size (sentence-aware).
    chunks: List[str] = []
    for block in packed:
        words = block.split()
        if len(words) <= size:
            chunks.append(block)
            continue

        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(block) if s.strip()]
        current: List[str] = []
        current_len = 0
        for sentence in sentences:
            sentence_len = len(sentence.split())
            if sentence_len > size:
                if current:
                    chunks.append(" ".join(current))
                    current, current_len = [], 0
                chunks.extend(_split_oversized(sentence, size))
                continue
            if current_len + sentence_len + 1 > size and current:
                chunks.append(" ".join(current))
                current, current_len = [], 0
            current.append(sentence)
            current_len += sentence_len
        if current:
            chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]


def chunk_extracted_pages(pages: List["ExtractedPage"]) -> List[Chunk]:
    """Turn extracted pages into metadata-carrying chunks."""
    from app.rag.extraction import ExtractedPage  # local import avoids a cycle

    chunks: List[Chunk] = []
    for page in pages:
        texts = chunk_page_text(page.text, page.source, page.page)
        doc_type = document_type_from_filename(page.source)
        for index, text in enumerate(texts):
            chunks.append(
                Chunk(
                    text=text,
                    source=page.source,
                    page=page.page,
                    chunk_index=index,
                    document_type=doc_type,
                )
            )
    logger.info("Created %d chunk(s) from %d page(s)", len(chunks), len(pages))
    return chunks
