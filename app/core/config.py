import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Soulrip API"
    api_prefix: str = "/api/v1"

    database_url: str = f"sqlite:///{BASE_DIR / 'soulrip.db'}"

    # NoDecode: 쉼표 구분 문자열을 pydantic-settings가 JSON으로 먼저 해석하다 실패하지 않게 한다.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # OpenAI - 챗봇, AI 인사이트
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()