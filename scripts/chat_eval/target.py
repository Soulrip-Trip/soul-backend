import asyncio
import threading
import time

from langsmith import traceable
from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import SessionLocal
from app.db.models import FestivalSchedule, Location
from app.services import chat_service
from app.services.rag_service import rag_service

settings = get_settings()

# answer_chat은 OpenAI 호출이 실패하면 예외 대신 fallback 답변(used_ai=False)을 돌려준다.
# 평가에서는 rate limit 같은 일시 오류가 점수를 오염시키지 않도록 몇 번 재시도한다.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SEC = 5

RAG_SECTION_HEADER = "[서울관광 실태조사·공공데이터 근거]"

# 챗봇은 비동기이고 공유 HTTP 클라이언트가 특정 이벤트 루프에 묶여 있으므로,
# 평가가 쓰는 여러 스레드가 하나의 백그라운드 이벤트 루프를 함께 사용한다.
_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _run(coroutine):
    global _loop
    with _loop_lock:
        if _loop is None:
            rag_service.startup()  # embedded RAG 인덱스를 한 번 로드한다. (서버 lifespan이 하는 일)
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, daemon=True, name="chat-eval-loop").start()
    return asyncio.run_coroutine_threadsafe(coroutine, _loop).result()


@traceable(run_type="retriever", name="retrieve_context")
def _retrieve(message: str, history: list[dict], language: str) -> dict:
    """answer_chat이 쓰는 것과 같은 검색을 수행하고, 평가에 필요한 DB 사실을 함께 돌려준다."""
    with SessionLocal() as db:
        sources, context = _run(chat_service.build_chat_context(db, message, language, history))

        content_ids = [source.id for source in sources if source.type in ("LOCATION", "FESTIVAL")]
        locations = {}
        schedule_dates: list[str] = []
        if content_ids:
            locations = {
                location.content_id: location
                for location in db.scalars(select(Location).where(Location.content_id.in_(content_ids)))
            }
            for start, end in db.execute(
                select(FestivalSchedule.start_date, FestivalSchedule.end_date)
                .join(Location, FestivalSchedule.location_id == Location.id)
                .where(Location.content_id.in_(content_ids))
            ):
                schedule_dates += [start.isoformat(), end.isoformat()]

    return {
        "sources": [
            {"type": source.type, "id": source.id, "title": source.title, "subtitle": source.subtitle}
            for source in sources
        ],
        "source_locations": [
            {
                "content_id": cid,
                "title": locations[cid].title,
                "district": locations[cid].district,
                "content_type": locations[cid].content_type,
            }
            for cid in content_ids
            if cid in locations
        ],
        "context": context,
        "rag_context": context.partition(RAG_SECTION_HEADER)[2],
        "schedule_dates": schedule_dates,
    }


@traceable(run_type="chain", name="answer_chat")
def _answer(message: str, history: list[dict], language: str) -> dict:
    with SessionLocal() as db:
        response = _run(chat_service.answer_chat(db, message, history, language))
    return {"answer": response.answer, "used_ai": response.used_ai, "suggestions": response.suggestions}


def _answer_with_retry(message: str, history: list[dict], language: str) -> tuple[dict, int]:
    attempts = 0
    while True:
        attempts += 1
        result = _answer(message, history, language)
        if result["used_ai"] or not settings.openai_api_key or attempts >= MAX_ATTEMPTS:
            return result, attempts
        time.sleep(RETRY_BACKOFF_SEC * attempts)


def make_target(retrieval_only: bool):
    def chatbot_target(inputs: dict) -> dict:
        message = inputs["message"]
        history = inputs.get("history") or []
        language = inputs.get("language") or "ko"

        outputs = _retrieve(message, history, language)
        if retrieval_only:
            return outputs

        result, attempts = _answer_with_retry(message, history, language)
        return {**outputs, **result, "attempts": attempts}

    return chatbot_target
