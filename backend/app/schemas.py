"""Pydantic schemas for the chat API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        examples=["How long does a refund take after approval?"],
    )


class SourceInfo(BaseModel):
    document: str
    page: int
    document_type: Optional[str] = None
    score: Optional[float] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceInfo] = []
    # Similarity score of the best retrieved chunk (useful for debugging)
    score: Optional[float] = None


class HealthResponse(BaseModel):
    status: str = "ok"
