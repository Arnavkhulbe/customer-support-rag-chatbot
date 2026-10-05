"""FastAPI application entrypoint.

Run from the backend directory with:
    uvicorn app.main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.chat import router as chat_router
from app.config import settings
from app.schemas import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="ShopSphere AI Customer Support",
    description="RAG-based customer-support chatbot API (FastAPI + Pinecone + local embeddings)",
    version="1.0.0",
)

# CORS: restricted to the configured frontend origins (no wildcard).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe: GET /health -> {"status": "ok"}"""
    return HealthResponse()
