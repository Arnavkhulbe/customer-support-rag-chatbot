"""LLM answer generation via the Groq API.

The generator is independent from Pinecone: it receives the user question and
the already-retrieved context and produces the final natural-language answer.
The Groq client is initialized with the `groq` SDK using GROQ_API_KEY.
"""

import logging
from typing import List

from groq import Groq

from app.config import settings
from app.rag.prompts import build_messages
from app.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)

# Safe fallback shown when retrieval found nothing relevant (rule 4/5 of the
# system prompt — the LLM must not invent policies).
NO_CONTEXT_FALLBACK = (
    "I couldn't find this information in the available ShopSphere company documents."
)


class LLMGenerationError(RuntimeError):
    """Raised when the Groq call fails."""


def generate_answer(question: str, chunks: List[RetrievedChunk]) -> str:
    """Call the configured Groq model with system prompt + context + question."""
    if not settings.groq_api_key:
        raise LLMGenerationError(
            "GROQ_API_KEY is not set. Add it to the root .env file (see .env.example)."
        )

    messages = build_messages(question, chunks)
    client = Groq(api_key=settings.groq_api_key)

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_answer_tokens,
        )
    except Exception as exc:  # network, auth, rate-limit errors all land here
        logger.error("Groq request failed: %s", exc)
        raise LLMGenerationError(f"LLM request failed: {exc}") from exc

    answer = (response.choices[0].message.content or "").strip() if response.choices else ""
    if not answer:
        raise LLMGenerationError("The LLM returned an empty answer.")
    return answer
