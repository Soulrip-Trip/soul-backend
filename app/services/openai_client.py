"""OpenAI chat completions 호출.

- 앱 공유 AsyncClient(keep-alive 연결 재사용)를 사용한다.
- asyncio.Semaphore로 동시 호출 수를 제한해 순간 트래픽에서 429를 줄인다.
- 키가 없거나 호출이 실패하면 예외를 그대로 올려 호출자가 fallback을 결정한다.
"""

import asyncio

from app.core.config import get_settings
from app.core.http_client import get_http_client

settings = get_settings()
API_URL = "https://api.openai.com/v1/chat/completions"

_semaphore: asyncio.Semaphore | None = None


class OpenAIUnavailableError(RuntimeError):
    pass


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, settings.openai_max_concurrency))
    return _semaphore


def _extract_text(payload: dict) -> str:
    choices = payload.get("choices") or [{}]
    return ((choices[0].get("message") or {}).get("content") or "").strip()


async def generate_text(
    messages: list[dict],
    system_instruction: str | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """messages: [{"role": "user" | "assistant", "content": str}, ...]"""
    if not settings.openai_api_key:
        raise OpenAIUnavailableError("OPENAI_API_KEY가 설정되지 않았습니다.")

    body_messages = list(messages)
    if system_instruction:
        body_messages.insert(0, {"role": "system", "content": system_instruction})
    body = {
        "model": settings.openai_model,
        "messages": body_messages,
        "max_completion_tokens": max_output_tokens or settings.openai_max_output_tokens,
    }

    async with _get_semaphore():
        response = await get_http_client().post(
            API_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=body,
            timeout=settings.openai_timeout_seconds,
        )
    response.raise_for_status()
    return _extract_text(response.json())
