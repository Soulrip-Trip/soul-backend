"""(선택) Gemini 임베딩.

기본 인덱스는 BM25만 사용해 검색 시 외부 API 호출이 0회다.
`build_index.py --embed`로 빌드하면 chunk 임베딩을 빌드 시점에 한 번만 계산해 저장하고,
검색 시에는 질의 1건만 임베딩한다(동일 질의는 캐시).
"""

import asyncio
import logging
import time

import httpx
import numpy as np

logger = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_DIMENSION = 768
BATCH_SIZE = 100
MAX_RETRIES = 5


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


def _request(model: str, text: str, task_type: str, dimension: int) -> dict:
    return {
        "model": f"models/{model}",
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": dimension,
    }


def embed_documents(
    texts: list[str],
    api_key: str,
    model: str,
    dimension: int = DEFAULT_DIMENSION,
) -> np.ndarray:
    """빌드 시점 전용(동기). 429/5xx는 지수 백오프로 재시도한다."""
    vectors: list[list[float]] = []
    with httpx.Client(timeout=60.0) as client:
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start:start + BATCH_SIZE]
            body = {"requests": [_request(model, text[:6000], "RETRIEVAL_DOCUMENT", dimension) for text in batch]}
            for attempt in range(MAX_RETRIES):
                response = client.post(
                    f"{API_BASE}/{model}:batchEmbedContents",
                    headers={"x-goog-api-key": api_key},
                    json=body,
                )
                if response.status_code in (429, 500, 502, 503) and attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning("임베딩 요청 재시도(%s) %ss 후: status=%s", attempt + 1, wait, response.status_code)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                break
            vectors.extend(item["values"] for item in response.json()["embeddings"])
            logger.info("임베딩 %s/%s", min(start + BATCH_SIZE, len(texts)), len(texts))
    return _normalize(np.asarray(vectors, dtype=np.float32))


async def embed_query(
    client: httpx.AsyncClient,
    text: str,
    api_key: str,
    model: str,
    dimension: int,
    timeout: float = 5.0,
) -> np.ndarray:
    body = _request(model, text, "RETRIEVAL_QUERY", dimension)
    body.pop("model")
    response = await asyncio.wait_for(
        client.post(
            f"{API_BASE}/{model}:embedContent",
            headers={"x-goog-api-key": api_key},
            json=body,
        ),
        timeout=timeout,
    )
    response.raise_for_status()
    values = np.asarray(response.json()["embedding"]["values"], dtype=np.float32)
    return _normalize(values)
