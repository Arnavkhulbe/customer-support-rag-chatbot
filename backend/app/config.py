"""Application configuration.

All values come from environment variables (loaded from backend/.env or the
project-root .env). No secrets are hard-coded anywhere in this project.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent

# backend/.env wins over root/.env; neither overrides real environment variables
load_dotenv(BACKEND_DIR / ".env", override=False)
load_dotenv(ROOT_DIR / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    # --- LLM (answer generation only; retrieval never uses the LLM) ---
    # Groq is the LLM provider. openai/gpt-oss-120b is Groq's flagship openly
    # available production model (the prefix is the release org, not a service).
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    temperature: float = 0.2
    max_answer_tokens: int = 600

    # --- Pinecone (vector database) ---
    pinecone_api_key: str = ""
    pinecone_index_name: str = "shopsphere-support"
    pinecone_namespace: str = "policies"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # --- Embeddings (free / local model, 384 dimensions) ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # --- Knowledge base & ingestion ---
    knowledge_dir: str = str(ROOT_DIR / "knowledge")
    # Chunk sizes are in words (~1.3 tokens/word). 180 words (~240 tokens) fits
    # all-MiniLM-L6-v2's 256-token input window; larger values are supported but
    # only the first ~256 tokens of a chunk influence its embedding.
    chunk_size: int = 180
    chunk_overlap: int = 40

    # --- Retrieval ---
    top_k: int = 4
    # Calibrated against the demo knowledge base: off-topic questions score
    # < 0.13, in-scope questions score > 0.19. The system prompt provides a
    # second layer of defense for questions that pass this gate.
    min_relevance_score: float = 0.20

    # --- API ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"

    # ------------------------------------------------------------------
    @property
    def knowledge_path(self) -> Path:
        path = Path(self.knowledge_dir)
        return path if path.is_absolute() else (ROOT_DIR / path).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_required_keys(self) -> None:
        missing = [
            name
            for name, value in (
                ("GROQ_API_KEY", self.groq_api_key),
                ("PINECONE_API_KEY", self.pinecone_api_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". Add the key(s) to the root .env file (see .env.example)."
            )


settings = Settings()
