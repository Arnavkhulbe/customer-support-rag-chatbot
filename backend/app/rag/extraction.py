"""PDF text extraction for the ShopSphere knowledge base.

Every page of every PDF becomes an extracted unit that keeps its source
filename and page number so answers can be attributed.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

from pypdf import PdfReader

logger = logging.getLogger(__name__)


class PDFExtractionError(RuntimeError):
    """Raised when a PDF cannot be read — never silently ignore this."""


@dataclass
class ExtractedPage:
    source: str   # e.g. "return-policy.pdf"
    page: int     # 1-based page number
    text: str


def extract_pdf(pdf_path: Path) -> List[ExtractedPage]:
    """Extract text page by page from a single PDF."""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        raise PDFExtractionError(
            f"Cannot open PDF '{pdf_path.name}': {exc}. "
            "The file may be corrupted or password-protected."
        ) from exc

    pages: List[ExtractedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            # A single unreadable page shouldn't kill the whole document,
            # but it must be visible in the logs.
            logger.error("Failed to extract text from %s page %d: %s", pdf_path.name, index, exc)
            text = ""

        text = text.replace("\x00", "").strip()
        if text:
            pages.append(ExtractedPage(source=pdf_path.name, page=index, text=text))
        else:
            logger.warning(
                "No extractable text on %s page %d (scanned image page?)", pdf_path.name, index
            )

    if not pages:
        raise PDFExtractionError(
            f"No text could be extracted from '{pdf_path.name}'. "
            "If the PDF is a scan, run OCR on it first."
        )
    return pages


def extract_all_pdfs(knowledge_dir: Path) -> List[ExtractedPage]:
    """Extract text from every PDF in the knowledge directory."""
    if not knowledge_dir.is_dir():
        raise PDFExtractionError(
            f"Knowledge directory not found: {knowledge_dir}. "
            "Place the ShopSphere PDFs there and run ingestion again."
        )

    pdf_files = sorted(knowledge_dir.glob("*.pdf"))
    if not pdf_files:
        raise PDFExtractionError(f"No PDF files found in {knowledge_dir}.")

    all_pages: List[ExtractedPage] = []
    for pdf_path in pdf_files:
        pages = extract_pdf(pdf_path)
        logger.info("Extracted %d page(s) from %s", len(pages), pdf_path.name)
        all_pages.extend(pages)
    return all_pages
