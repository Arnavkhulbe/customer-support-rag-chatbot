"""Pinecone vector store helpers.

Handles index creation/reuse and upsert/query within the configured namespace.
Chunk text lives in vector metadata so the app can retrieve the actual text
without ever sending raw vectors to the LLM.
"""

import hashlib
import logging
from typing import Dict, List, Optional

from pinecone import Pinecone, ServerlessSpec

from app.config import settings
from app.rag.chunking import Chunk

logger = logging.getLogger(__name__)

# Metadata fields stored with every vector. `text` is essential: it is what
# gets injected into the prompt as retrieved context.
_METADATA_KEYS = ("text", "source", "page", "document_type", "chunk_id")


def _pc() -> Pinecone:
    settings.validate_required_keys()
    return Pinecone(api_key=settings.pinecone_api_key)


def ensure_index() -> "Pinecone.Index":
    """Create the index (384-dim, cosine) if missing, then return a handle."""
    pc = _pc()
    name = settings.pinecone_index_name

    existing = {index["name"] for index in pc.list_indexes()}
    if name in existing:
        logger.info("Using existing Pinecone index '%s'", name)
    else:
        logger.info(
            "Creating Pinecone index '%s' (dimension=%d, metric=cosine)",
            name,
            settings.embedding_dimension,
        )
        pc.create_index(
            name=name,
            dimension=settings.embedding_dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=settings.pinecone_cloud, region=settings.pinecone_region),
        )
        # Serverless indexes are not immediately queryable.
        # Poll until ready (bounded loop; ~60s max).
        for _ in range(60):
            status = pc.describe_index(name).status
            if status and status.get("ready"):
                break
        else:
            raise RuntimeError(f"Pinecone index '{name}' did not become ready in time.")
        logger.info("Pinecone index '%s' is ready", name)

    return pc.Index(name)


def deterministic_chunk_id(chunk: Chunk) -> str:
    """Stable ID per (document, page, chunk) so re-ingestion upserts instead
    of creating duplicates. A hash keeps IDs unique even if the same page is
    re-chunked differently."""
    digest = hashlib.sha1(
        f"{chunk.source}|{chunk.page}|{chunk.chunk_index}".encode("utf-8")
    ).hexdigest()[:12]
    return f"{chunk.source}-p{chunk.page}-c{chunk.chunk_index}-{digest}"


def upsert_chunks(chunks: List[Chunk]) -> int:
    """Embed and upsert chunks with deterministic IDs. Returns count upserted."""
    from app.rag.embeddings import embed_texts

    if not chunks:
        return 0

    index = ensure_index()
    embeddings = embed_texts([c.text for c in chunks])

    vectors = [
        (
            deterministic_chunk_id(chunk),
            embedding,
            {
                "text": chunk.text,
                "source": chunk.source,
                "page": chunk.page,
                "document_type": chunk.document_type,
                "chunk_id": deterministic_chunk_id(chunk),
            },
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]

    namespace = settings.pinecone_namespace
    # Pinecone recommends batches of <= 100 vectors.
    for start in range(0, len(vectors), 100):
        batch = vectors[start : start + 100]
        index.upsert(vectors=batch, namespace=namespace)

    logger.info(
        "Upserted %d vector(s) into index '%s' namespace '%s'",
        len(vectors),
        settings.pinecone_index_name,
        namespace,
    )
    return len(vectors)


def query_chunks(
    query_embedding: List[float],
    top_k: Optional[int] = None,
) -> List[Dict]:
    """Run a similarity search and return matches with their metadata text."""
    index = ensure_index()
    k = top_k or settings.top_k
    result = index.query(
        vector=query_embedding,
        top_k=k,
        namespace=settings.pinecone_namespace,
        include_metadata=True,
    )
    matches = []
    for match in result.get("matches", []):
        metadata = match.get("metadata") or {}
        matches.append(
            {
                "text": metadata.get("text", ""),
                "source": metadata.get("source", "unknown"),
                "page": int(metadata.get("page", 0) or 0),
                "document_type": metadata.get("document_type"),
                "chunk_id": metadata.get("chunk_id"),
                "score": float(match.get("score", 0.0)),
            }
        )
    return matches
