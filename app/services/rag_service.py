"""서울관광 실태조사·공공데이터 RAG 검색.

RAG_MODE
- embedded: rag-server/index를 백엔드 프로세스 시작 시 한 번 로드해 직접 검색(배포 서비스 1개로 운영)
- remote  : 별도 rag-server의 POST /api/v1/rag/search 호출(서비스 분리 운영)
- off     : 사용하지 않음

어떤 모드든 실패하면 빈 결과를 돌려주고 챗봇은 기존 DB 검색만으로 답한다(RAG는 보조 근거).
"""

import logging
import sys
from dataclasses import dataclass, field

from anyio import to_thread

from app.core.cache import TTLCache
from app.core.config import get_settings
from app.core.http_client import get_http_client

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass(frozen=True)
class RagHit:
    id: str
    doc_id: str
    collection: str
    title: str
    year: int | None
    audience_label: str
    status: str | None
    status_label: str
    location: str
    text: str
    score: float
    meta: dict = field(default_factory=dict)

    @property
    def is_preliminary(self) -> bool:
        return self.status == "preliminary"

    @classmethod
    def from_payload(cls, item: dict) -> "RagHit":
        def pick(snake: str, camel: str, default=None):
            return item.get(snake, item.get(camel, default))

        return cls(
            id=item["id"],
            doc_id=pick("doc_id", "docId", ""),
            collection=item.get("collection", ""),
            title=item.get("title", ""),
            year=item.get("year"),
            audience_label=pick("audience_label", "audienceLabel", ""),
            status=item.get("status"),
            status_label=pick("status_label", "statusLabel", ""),
            location=item.get("location", ""),
            text=item.get("text", ""),
            score=float(item.get("score") or 0.0),
            meta=item.get("meta") or {},
        )


class RagService:
    def __init__(self) -> None:
        self._retriever = None
        self._error: str | None = None
        self._cache = TTLCache("rag", maxsize=512, ttl=600)

    # ------------------------------------------------------------------
    def startup(self) -> None:
        """embedded 모드에서 인덱스를 미리 로드한다(첫 요청 지연 방지). lifespan에서 스레드로 실행."""
        if settings.rag_mode != "embedded":
            return
        try:
            rag_dir = str(settings.rag_server_dir)
            if rag_dir not in sys.path:
                sys.path.append(rag_dir)
            from rag.retriever import get_retriever

            self._retriever = get_retriever(settings.resolved_rag_index_dir)
            logger.info("RAG 인덱스 로드: %s", self._retriever.info())
        except Exception as error:  # 인덱스가 없어도 API 서버는 떠야 한다.
            self._error = f"{type(error).__name__}: {error}"
            logger.warning("RAG 인덱스를 로드하지 못해 RAG 없이 동작합니다: %s", self._error)

    def status(self) -> str:
        if settings.rag_mode == "off":
            return "off"
        if settings.rag_mode == "remote":
            return "remote" if settings.rag_server_url else "remote:not-configured"
        if self._retriever is not None:
            return f"embedded:ready({self._retriever.info()['chunks']} chunks)"
        return f"embedded:unavailable({self._error or 'not loaded'})"

    # ------------------------------------------------------------------
    async def search(self, query: str, top_k: int | None = None) -> list[RagHit]:
        query = " ".join(query.split())
        if not query or settings.rag_mode == "off":
            return []
        top_k = top_k or settings.rag_top_k
        key = (query, top_k)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            if settings.rag_mode == "remote":
                hits = await self._search_remote(query, top_k)
            else:
                hits = await self._search_embedded(query, top_k)
        except Exception as error:
            logger.warning("RAG 검색 실패, DB 검색만 사용합니다: %r", error)
            return []

        self._cache.set(key, hits)
        return hits

    async def _search_embedded(self, query: str, top_k: int) -> list[RagHit]:
        if self._retriever is None:
            return []
        result = await to_thread.run_sync(
            lambda: self._retriever.search(query, top_k=top_k, max_chars=settings.rag_max_chars_per_hit)
        )
        return [RagHit.from_payload(item) for item in result["hits"]]

    async def _search_remote(self, query: str, top_k: int) -> list[RagHit]:
        if not settings.rag_server_url:
            return []
        headers = {"X-RAG-Key": settings.rag_api_key} if settings.rag_api_key else {}
        response = await get_http_client().post(
            f"{settings.rag_server_url.rstrip('/')}/api/v1/rag/search",
            json={"query": query, "topK": top_k, "maxCharsPerHit": settings.rag_max_chars_per_hit},
            headers=headers,
            timeout=settings.rag_timeout_seconds,
        )
        response.raise_for_status()
        return [RagHit.from_payload(item) for item in response.json().get("hits", [])]


rag_service = RagService()
