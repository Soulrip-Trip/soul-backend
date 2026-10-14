"""Gemini generateContent 호출.

- 앱 공유 AsyncClient(keep-alive 연결 재사용)를 사용한다.
- asyncio.Semaphore로 동시 호출 수를 제한해 순간 트래픽에서 429를 줄인다.
- 키가 없거나 호출이 실패하면 예외를 그대로 올려 호출자가 fallback을 결정한다.
"""

import asyncio

from app.core.config import get_settings
from app.core.http_client import get_http_client

settings = get_settings()
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

_semaphore: asyncio.Semaphore | None = None


class GeminiUnavailableError(RuntimeError):
    pass


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, settings.gemini_max_concurrency))
    return _semaphore


def _extract_text(payload: dict) -> str:
    candidates = payload.get("candidates") or [{}]
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts).strip()


async def generate_text(
    contents: list[dict],
    system_instruction: str | None = None,
    max_output_tokens: int | None = None,
) -> str:
    if not settings.gemini_api_key:
        raise GeminiUnavailableError("GEMINI_API_KEY가 설정되지 않았습니다.")

    body: dict = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_output_tokens or settings.gemini_max_output_tokens},
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    async with _get_semaphore():
        response = await get_http_client().post(
            f"{API_BASE}/{settings.gemini_model}:generateContent",
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=body,
            timeout=settings.gemini_timeout_seconds,
        )
    response.raise_for_status()
    return _extract_text(response.json())
