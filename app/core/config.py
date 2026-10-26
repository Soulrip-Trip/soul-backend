import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Soulrip API"
    api_prefix: str = "/api/v1"

    database_url: str = f"sqlite:///{BASE_DIR / 'soulrip.db'}"
    # SQLite WAL 모드: 읽기와 쓰기가 서로를 막지 않아 동시 요청에서 'database is locked'를 줄인다.
    sqlite_wal: bool = True

    # NoDecode: 쉼표 구분 문자열을 pydantic-settings가 JSON으로 먼저 해석하다 실패하지 않게 한다.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # OpenAI - 챗봇, AI 인사이트
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    # 같은 날 인사이트는 TTL 동안 재사용한다(0이면 매 요청 생성).
    ai_insight_cache_ttl_seconds: int = 600

    openai_timeout_seconds: float = 30.0
    openai_max_output_tokens: int = 2048
    # 동시에 OpenAI로 나가는 챗봇 요청 수 상한(429 Too Many Requests 완화)
    openai_max_concurrency: int = 8

    # 챗봇 응답 캐시: 같은 언어·질문·대화 맥락이면 TTL 동안 OpenAI를 다시 호출하지 않는다.
    chat_cache_ttl_seconds: int = 600

    # RAG (서울관광 실태조사·공공데이터)
    # embedded: 백엔드 프로세스 안에서 rag-server 인덱스를 직접 로드
    # remote  : 별도 rag-server(HTTP)를 호출
    # off     : RAG 미사용(기존 DB 검색만)
    rag_mode: Literal["embedded", "remote", "off"] = "embedded"
    rag_server_dir: Path = BASE_DIR / "rag-server"
    rag_index_dir: Path | None = None
    rag_server_url: str | None = None
    rag_api_key: str | None = None
    rag_timeout_seconds: float = 5.0
    rag_top_k: int = 4
    rag_max_chars_per_hit: int = 700

    # 메타 API(카테고리·자치구 집계) 캐시
    meta_cache_ttl_seconds: int = 300

    admin_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            if value.strip().startswith("["):
                return json.loads(value)

            return [
                item.strip()
                for item in value.split(",")
                if item.strip()
            ]

        return value

    @property
    def resolved_rag_index_dir(self) -> Path:
        return self.rag_index_dir or self.rag_server_dir / "index"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
