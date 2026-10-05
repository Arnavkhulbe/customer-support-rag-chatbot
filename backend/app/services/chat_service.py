"""Chat service: orchestrates retrieval + generation for the API layer."""

import logging
from typing import List

from app.config import settings
from app.rag.generator import NO_CONTEXT_FALLBACK, generate_answer
from app.rag.retriever import RetrievedChunk, retrieve
from app.schemas import ChatResponse, SourceInfo

logger = logging.getLogger(__name__)


def answer_question(question: str) -> ChatResponse:
    """Run the RAG flow for one user question.

    1. Embed the question locally (all-MiniLM-L6-v2).
    2. Search Pinecone for the top-k relevant policy chunks.
    3. Apply the relevance threshold; if nothing is relevant enough, return a
       safe "not found" answer WITHOUT calling the LLM (it must not invent).
    4. Otherwise, build the prompt and generate the answer with the LLM.
    """
    chunks = retrieve(question)

    if not chunks:
        logger.info("No relevant chunks for question; returning safe fallback.")
        return ChatResponse(answer=NO_CONTEXT_FALLBACK, sources=[], score=None)

    answer = generate_answer(question, chunks)

    # Deduplicate sources by (document, page) while keeping order.
    seen: set = set()
    sources: List[SourceInfo] = []
    for chunk in chunks:
        key = (chunk.source, chunk.page)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            SourceInfo(
                document=chunk.source,
                page=chunk.page,
                document_type=chunk.document_type,
                score=round(chunk.score, 4),
            )
        )

    return ChatResponse(
        answer=answer,
        sources=sources,
        score=round(max(c.score for c in chunks), 4),
    )
