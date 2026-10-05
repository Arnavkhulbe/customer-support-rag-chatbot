"""Retrieval: embed the user question, search Pinecone, apply threshold."""

import logging
from dataclasses import dataclass
from typing import List

from app.config import settings
from app.rag import pinecone_store
from app.rag.embeddings import embed_query

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    page: int
    score: float
    document_type: str | None = None


def retrieve(question: str, top_k: int | None = None) -> List[RetrievedChunk]:
    """Return top-k chunks above the minimum relevance score."""
    query_vector = embed_query(question)
    matches = pinecone_store.query_chunks(query_vector, top_k=top_k)

    results: List[RetrievedChunk] = []
    for match in matches:
        if match["score"] < settings.min_relevance_score:
            continue
        results.append(
            RetrievedChunk(
                text=match["text"],
                source=match["source"],
                page=match["page"],
                score=match["score"],
                document_type=match.get("document_type"),
            )
        )

    logger.info(
        "Retrieved %d/%d chunk(s) above threshold %.2f for question: %.80s",
        len(results),
        len(matches),
        settings.min_relevance_score,
        question,
    )
    return results
