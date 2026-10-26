from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAG_ROOT = Path(__file__).resolve().parents[1]


class RagSettings(BaseSettings):
    app_name: str = "Soulrip RAG Server"
    api_prefix: str = "/api/v1/rag"

    data_dir: Path = RAG_ROOT / "data"
    index_dir: Path = RAG_ROOT / "index"

    # 백엔드 → RAG 서버 내부 호출 인증. 비어 있으면 인증하지 않는다(로컬 개발용).
    rag_api_key: str | None = None

    # (선택) dense 검색용 Gemini 임베딩
    gemini_api_key: str | None = None
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = 768
    embedding_timeout_seconds: float = 5.0

    default_top_k: int = 4
    max_top_k: int = 10
    max_chars_per_hit: int = 700
    cache_ttl_seconds: int = 600
    cache_max_entries: int = 512

    model_config = SettingsConfigDict(
        env_file=RAG_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> RagSettings:
    return RagSettings()
