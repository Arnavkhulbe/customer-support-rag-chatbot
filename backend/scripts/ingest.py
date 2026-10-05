"""Ingestion pipeline: PDF -> extract -> chunk -> embed -> Pinecone.

Run from the backend directory:
    python scripts/ingest.py

The script is idempotent: deterministic vector IDs mean re-running it
upserts/replaces the same vectors instead of creating duplicates.
"""

import logging
import sys
from pathlib import Path

# Make `app` importable when running as a script from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.rag.chunking import chunk_extracted_pages  # noqa: E402
from app.rag.embeddings import get_embedding_model  # noqa: E402
from app.rag.extraction import PDFExtractionError, extract_all_pdfs  # noqa: E402
from app.rag.pinecone_store import upsert_chunks  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingest")


def main() -> int:
    logger.info("=== ShopSphere knowledge-base ingestion ===")
    logger.info("Knowledge directory: %s", settings.knowledge_path)
    logger.info(
        "Chunking: size=%d words, overlap=%d | top_k=%d | min_score=%.2f",
        settings.chunk_size,
        settings.chunk_overlap,
        settings.top_k,
        settings.min_relevance_score,
    )

    try:
        settings.validate_required_keys()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    # 1. Load the (free, local) embedding model once, up front.
    get_embedding_model()

    # 2. Extract text from every PDF in knowledge/.
    try:
        pages = extract_all_pdfs(settings.knowledge_path)
    except PDFExtractionError as exc:
        logger.error("Extraction failed: %s", exc)
        return 1

    logger.info("Extracted %d page(s) total", len(pages))

    # 3. Chunk the extracted text.
    chunks = chunk_extracted_pages(pages)
    if not chunks:
        logger.error("Chunking produced 0 chunks — nothing to ingest.")
        return 1
    logger.info("Created %d chunk(s)", len(chunks))

    # 4. Embed + 5. upsert into Pinecone (deterministic IDs => no duplicates).
    try:
        count = upsert_chunks(chunks)
    except Exception as exc:  # noqa: BLE001
        logger.error("Pinecone upsert failed: %s", exc)
        return 1

    logger.info("=== Ingestion complete: %d vector(s) stored ===", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
