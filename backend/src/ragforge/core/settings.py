from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAGFORGE_", env_file=".env", extra="ignore")
    database_path: str = "ragforge.db"
    api_key: str | None = None
    provider_url: str | None = None
    provider_api_key: str | None = None
    provider_model: str = "gpt-4o-mini"
    provider_timeout_seconds: float = 15.0
    max_input_chars: int = 1_000_000
    max_upload_bytes: int = 10_000_000
    max_top_k: int = 20
    embedder: str | None = None
    reranker: str | None = None

    @property
    def provider_enabled(self) -> bool:
        return bool(self.provider_url)

    def public(self) -> dict:
        return {
            "database": "sqlite",
            "provider": "openai-compatible" if self.provider_enabled else "offline-extractive",
            "provider_configured": self.provider_enabled,
            "generation_mode": "provider" if self.provider_enabled else "offline-extractive",
            "embedder_configured": bool(self.embedder),
            "dense_available": bool(self.embedder),
            "reranker_configured": bool(self.reranker),
            "reranker_available": bool(self.reranker),
            "retrieval_modes": ["sparse", "dense", "hybrid"],
            "default_retrieval_mode": "hybrid",
            "pdf_supported": True,
            "max_upload_bytes": self.max_upload_bytes,
            "supported_extensions": [".txt", ".md", ".html", ".pdf"],
            "limits": {
                "max_input_chars": self.max_input_chars,
                "max_upload_bytes": self.max_upload_bytes,
                "max_top_k": self.max_top_k,
            },
        }
