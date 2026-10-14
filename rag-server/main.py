"""Soulrip RAG Server.

백엔드(app/services/rag_service.py)가 RAG_MODE=remote일 때 호출하는 검색 전용 API.
- 인덱스는 서버 시작 시 한 번만 메모리에 올린다(요청마다 파일·원천 자료를 읽지 않는다).
- 검색은 로컬 BM25라 기본적으로 외부 API 호출과 토큰 비용이 없다.
- 동일 질의는 TTL 캐시로 재계산하지 않는다.

실행: (rag-server 디렉터리에서) uvicorn main:app --port 8001
"""

import logging
import time
from contextlib import asynccontextmanager

import httpx
from anyio import to_thread
from fastapi import Depends, FastAPI, Header, HTTPException, status

from rag.cache import TTLCache
from rag.manifest import load_manifest
from rag.retriever import Retriever, get_retriever
from rag.schemas import HealthResponse, SearchRequest, SearchResponse
from rag.settings import get_settings

logger = logging.getLogger("rag_server")
settings = get_settings()

state: dict = {"retriever": None, "error": None, "http": None}
search_cache = TTLCache(maxsize=settings.cache_max_entries, ttl=settings.cache_ttl_seconds)
vector_cache = TTLCache(maxsize=settings.cache_max_entries, ttl=24 * 3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        state["retriever"] = await to_thread.run_sync(get_retriever, settings.index_dir)
        logger.info("RAG 인덱스 로드 완료: %s", state["retriever"].info())
    except FileNotFoundError:
        state["error"] = f"인덱스가 없습니다({settings.index_dir}). `python -m scripts.build_index`를 먼저 실행하세요."
        logger.error(state["error"])
    except ValueError as error:
        state["error"] = str(error)
        logger.error(state["error"])
    state["http"] = httpx.AsyncClient(timeout=settings.embedding_timeout_seconds)
    yield
    await state["http"].aclose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="서울관광 실태조사·서울 관광 공공데이터 검색(RAG) API",
    lifespan=lifespan,
)


def verify_key(x_rag_key: str | None = Header(default=None, alias="X-RAG-Key")) -> None:
    if settings.rag_api_key and x_rag_key != settings.rag_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="RAG API 키가 올바르지 않습니다.")


def require_retriever() -> Retriever:
    retriever = state["retriever"]
    if retriever is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=state["error"])
    return retriever


async def _query_vector(retriever: Retriever, query: str):
    """dense 인덱스와 키가 모두 있을 때만 질의 1건을 임베딩한다. 실패하면 BM25만 사용한다."""
    if not retriever.has_dense or not settings.gemini_api_key:
        return None
    cached = vector_cache.get(query)
    if cached is not None:
        return cached
    from rag.embeddings import embed_query

    try:
        vector = await embed_query(
            state["http"],
            query,
            api_key=settings.gemini_api_key,
            model=retriever.meta.get("embedding_model") or settings.gemini_embedding_model,
            dimension=retriever.meta.get("embedding_dimension") or settings.embedding_dimension,
            timeout=settings.embedding_timeout_seconds,
        )
    except Exception as error:  # 임베딩 실패는 검색 실패가 아니다.
        logger.warning("질의 임베딩 실패, BM25만 사용합니다: %r", error)
        return None
    vector_cache.set(query, vector)
    return vector


@app.get(f"{settings.api_prefix}/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    retriever = state["retriever"]
    return HealthResponse(
        status="ok" if retriever else "index_missing",
        index=retriever.info() if retriever else None,
        cache=search_cache.stats(),
        detail=state["error"],
    )


@app.get(f"{settings.api_prefix}/documents", tags=["rag"], dependencies=[Depends(verify_key)])
def documents() -> dict:
    """원천 자료 목록과 색인 여부(제외 사유 포함)."""
    retriever = state["retriever"]
    indexed = {item["id"]: item for item in (retriever.meta.get("documents", []) if retriever else [])}
    return {
        "items": [
            {
                "id": document.id,
                "title": document.title,
                "path": document.path,
                "collection": document.collection,
                "year": document.year,
                "audience": document.audience,
                "status": document.status,
                "publisher": document.publisher,
                "publishedAt": document.published_at,
                "sourceUrl": document.source_url,
                "indexed": document.index,
                "chunks": indexed.get(document.id, {}).get("chunks", 0),
                "excludeReason": document.exclude_reason,
            }
            for document in load_manifest(settings.data_dir)
        ]
    }


@app.post(
    f"{settings.api_prefix}/search",
    response_model=SearchResponse,
    tags=["rag"],
    dependencies=[Depends(verify_key)],
)
async def search(payload: SearchRequest, retriever: Retriever = Depends(require_retriever)) -> SearchResponse:
    started = time.perf_counter()
    top_k = min(payload.top_k or settings.default_top_k, settings.max_top_k)
    max_chars = payload.max_chars_per_hit or settings.max_chars_per_hit
    query = " ".join(payload.query.split())
    key = (query, top_k, tuple(payload.collections or ()), max_chars)

    cached = search_cache.get(key)
    if cached is None:
        vector = await _query_vector(retriever, query)
        result = await to_thread.run_sync(
            lambda: retriever.search(
                query,
                top_k=top_k,
                collections=list(payload.collections) if payload.collections else None,
                query_vector=vector,
                max_chars=max_chars,
            )
        )
        result["dense"] = vector is not None
        search_cache.set(key, result)
    else:
        result = cached

    return SearchResponse(
        query=query,
        hints=result["hints"],
        hits=result["hits"],
        dense=result["dense"],
        cached=cached is not None,
        took_ms=round((time.perf_counter() - started) * 1000, 2),
    )
