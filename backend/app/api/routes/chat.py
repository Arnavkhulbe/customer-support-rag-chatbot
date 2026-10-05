"""Chat API route."""

import logging

from fastapi import APIRouter, HTTPException

from app.schemas import ChatRequest, ChatResponse
from app.rag.generator import LLMGenerationError
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    """Answer a customer question using RAG over the ShopSphere knowledge base."""
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    try:
        return chat_service.answer_question(question)
    except LLMGenerationError as exc:
        # The LLM failed but retrieval was fine — surface a clear error.
        logger.error("Generation error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Missing keys, Pinecone not reachable/created, etc.
        logger.error("Backend configuration/runtime error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — last-resort guard so the UI never crashes blindly
        logger.exception("Unexpected error while answering question")
        raise HTTPException(status_code=500, detail="Internal server error.") from exc
