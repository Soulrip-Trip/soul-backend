"""지역 정보 챗봇.

흐름
1. 대화 기록 정규화(중복 질문·인사말 제거, 최근 10개, 메시지 길이 상한)
2. 응답 캐시 확인(같은 언어·질문·대화 맥락이면 Gemini 재호출 없음)
3. 비한국어 질문은 한국어 검색어로 변환(캐시)
4. SQLite 장소·축제·게시글 검색과 RAG(실태조사·공공데이터) 검색을 asyncio.gather로 동시에 수행
5. 검색 결과만 근거로 Gemini 호출, 실패하면 검색 결과 기반 fallback
"""

import asyncio
import logging
import re
from datetime import date

from anyio import to_thread
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.cache import TTLCache
from app.core.config import get_settings
from app.db.models import FestivalSchedule, Location, Post
from app.schemas.chat import ChatResponse, ChatSource
from app.services.gemini_client import generate_text
from app.services.rag_service import RagHit, rag_service

logger = logging.getLogger(__name__)
settings = get_settings()

HISTORY_LIMIT = 10
HISTORY_CHAR_LIMIT = 800
CONTEXT_CHAR_LIMIT = 7000
DB_SOURCE_LIMIT = 8
RAG_SOURCE_LIMIT = 3

chat_cache = TTLCache("chat", maxsize=256, ttl=settings.chat_cache_ttl_seconds)
translation_cache = TTLCache("chat-translation", maxsize=256, ttl=24 * 3600)

LANGUAGE_NAMES = {
    "ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Simplified Chinese",
    "fr": "French", "es": "Spanish", "de": "German",
}
FALLBACK_MESSAGES = {
    "ko": "저장된 서울 데이터에서 관련 결과를 찾지 못했어요. 장소명, 자치구 또는 여행 유형을 함께 입력해 주세요.",
    "en": "I couldn't find a related result in the saved Seoul data. Try a place name, district, or travel category.",
    "ja": "保存されたソウルのデータに関連する結果がありません。場所名、区、旅行カテゴリーを入力してください。",
    "zh": "在已保存的首尔数据中找不到相关结果。请输入地点名称、行政区或旅行类别。",
    "fr": "Aucun résultat associé n'a été trouvé dans les données de Séoul. Essayez un lieu, un arrondissement ou une catégorie.",
    "es": "No encontré resultados relacionados en los datos de Seúl. Prueba con un lugar, distrito o categoría.",
    "de": "In den gespeicherten Seoul-Daten wurde nichts Passendes gefunden. Versuche einen Ort, Bezirk oder eine Kategorie.",
}
RESULT_MESSAGES = {
    "ko": "저장된 서울 데이터에서 관련 결과를 찾았어요: {titles}. 아래 결과에서 상세 정보를 확인해 보세요.",
    "en": "I found related results in the saved Seoul data: {titles}. Check the results below for details.",
    "ja": "保存されたソウルのデータから関連情報が見つかりました：{titles}。詳細は下の結果をご覧ください。",
    "zh": "在已保存的首尔数据中找到了相关结果：{titles}。请在下方查看详细信息。",
    "fr": "Résultats trouvés dans les données de Séoul : {titles}. Consultez-les ci-dessous pour plus de détails.",
    "es": "Encontré resultados en los datos de Seúl: {titles}. Consulta los detalles abajo.",
    "de": "Passende Ergebnisse in den Seoul-Daten: {titles}. Details findest du unten.",
}
SUGGESTIONS = {
    "ko": ["혼자 걷기 좋은 곳", "이번 달 축제", "종로구 문화시설"],
    "en": ["Good places to walk alone", "Festivals this month", "Cultural spots in Jongno-gu"],
    "ja": ["一人で歩きやすい場所", "今月のお祭り", "鍾路区の文化施設"],
    "zh": ["适合独自散步的地方", "本月的庆典", "钟路区文化设施"],
    "fr": ["Balades à faire en solo", "Festivals du mois", "Lieux culturels à Jongno-gu"],
    "es": ["Lugares para pasear a solas", "Festivales de este mes", "Espacios culturales en Jongno-gu"],
    "de": ["Orte für Spaziergänge allein", "Festivals in diesem Monat", "Kulturorte in Jongno-gu"],
}

SYSTEM_PROMPT = (
    "너는 Soulrip 서울 혼행 여행 도우미다. 반드시 제공된 '검색된 데이터'만 근거로 답한다.\n"
    "- 데이터에 없는 영업시간·가격·축제 날짜를 추측하지 않는다. 근거가 없으면 모른다고 답한다.\n"
    "- 답변에 사용한 장소명·행사명은 제공된 표기를 그대로 쓴다.\n"
    "- 서울관광 실태조사 수치를 인용할 때는 연도와 조사 대상(내국인/외국인)을 함께 밝힌다.\n"
    "- '잠정치'로 표시된 자료는 확정 전 수치이므로 답변에도 잠정치임을 명시한다.\n"
    "- 서로 다른 연도·조사 대상의 수치를 하나의 수치처럼 합치지 않는다.\n"
    "- 실태조사는 관광객 전체의 경향이다. 개인 일정 추천에 쓸 때는 '조사에 따르면'처럼 근거임을 드러낸다.\n"
    "Answer concisely in {language}."
)

STOP_WORDS = {
    "추천", "추천해줘", "추천해주세요", "알려줘", "알려주세요", "보여줘", "보여주세요", "어디", "어떤", "대해",
    "있는", "좋은", "가볼만한", "서울", "서울시", "장소", "정보", "관련",
}
PARTICLES = ("에서", "으로", "에게", "에는", "이랑", "하고", "의", "을", "를", "은", "는", "이", "가", "에")


# ---------------------------------------------------------------------------
# DB 검색
# ---------------------------------------------------------------------------

def _search_terms(message: str) -> list[str]:
    terms: list[str] = []
    for raw in re.findall(r"[0-9A-Za-z가-힣]+", message):
        term = raw
        for particle in PARTICLES:
            if term.endswith(particle) and len(term) > len(particle) + 1:
                term = term[:-len(particle)]
                break
        if len(term) >= 2 and term not in STOP_WORDS and term not in terms:
            terms.append(term)
    return terms[:8]


def _first_schedules(db: Session, location_ids: list[int]) -> dict[int, FestivalSchedule]:
    """축제 장소별 가장 이른 일정. 원본 modifiedtime은 행사 일정이 아니므로 일정 테이블만 사용한다."""
    if not location_ids:
        return {}
    schedules = db.scalars(
        select(FestivalSchedule)
        .where(FestivalSchedule.location_id.in_(location_ids))
        .order_by(FestivalSchedule.start_date.asc())
    ).all()
    result: dict[int, FestivalSchedule] = {}
    for schedule in schedules:
        result.setdefault(schedule.location_id, schedule)
    return result


def _search_context(db: Session, message: str) -> tuple[list[ChatSource], list[str]]:
    terms = _search_terms(message)
    location_filters = []
    post_filters = []
    for term in terms:
        like = f"%{term}%"
        location_filters.extend((
            Location.title.ilike(like),
            Location.addr1.ilike(like),
            Location.addr2.ilike(like),
            Location.district.ilike(like),
            Location.content_type.ilike(like),
        ))
        post_filters.extend((Post.title.ilike(like), Post.content.ilike(like), Post.tags_json.ilike(like)))

    locations = []
    if location_filters:
        candidates = db.scalars(
            select(Location)
            .where(or_(*location_filters))
            .order_by(Location.is_featured.desc(), Location.solo_score.desc().nullslast(), Location.source_modified_at.desc())
            .limit(100)
        ).all()

        def relevance(item: Location) -> tuple[int, int, int]:
            title = item.title.lower()
            searchable = " ".join((item.title, item.addr1, item.addr2, item.district or "", item.content_type)).lower()
            matched = sum(term.lower() in searchable for term in terms)
            title_matches = sum(term.lower() in title for term in terms)
            return matched, title_matches, item.is_featured

        locations = sorted(candidates, key=relevance, reverse=True)[:8]
    if not locations and any(word in message for word in ("추천", "가볼", "혼자", "갈만한")):
        locations = db.scalars(
            select(Location)
            .where(Location.content_type_id.not_in((15, 25)))
            .order_by(Location.is_featured.desc(), Location.solo_score.desc().nullslast(), Location.source_modified_at.desc())
            .limit(8)
        ).all()

    posts = []
    if post_filters:
        posts = db.scalars(
            select(Post)
            .where(or_(*post_filters))
            .order_by(Post.created_at.desc())
            .limit(3)
        ).all()

    sources: list[ChatSource] = []
    context_lines: list[str] = []

    festival_schedules = _first_schedules(db, [item.id for item in locations if item.content_type_id == 15])
    for item in locations:
        sources.append(
            ChatSource(
                type="LOCATION",
                id=item.content_id,
                title=item.title,
                subtitle=f"{item.content_type} · {item.addr1}",
                image_url=item.first_image,
            )
        )
        date_text = ""
        if item.content_type_id == 15:
            schedule = festival_schedules.get(item.id)
            date_text = (
                f" / 축제 일정: {schedule.start_date}~{schedule.end_date}" if schedule else " / 축제 일정: 데이터 없음"
            )
        context_lines.append(
            f"장소: {item.title} / 유형: {item.content_type} / 주소: {item.addr1} {item.addr2} "
            f"/ 전화: {item.tel or '없음'} / 위도: {item.map_y or '없음'} / 경도: {item.map_x or '없음'}{date_text}"
        )

    for post in posts:
        sources.append(
            ChatSource(
                type="POST",
                id=str(post.id),
                title=post.title,
                subtitle=f"{post.nickname} · {post.type}",
            )
        )
        context_lines.append(f"커뮤니티 글: {post.title} / 내용: {post.content[:300]}")

    if ("축제" in message or "행사" in message) and not any(item.content_type_id == 15 for item in locations):
        schedules = db.execute(
            select(FestivalSchedule, Location)
            .join(Location, FestivalSchedule.location_id == Location.id)
            .where(FestivalSchedule.end_date >= date.today())
            .order_by(FestivalSchedule.start_date.asc())
            .limit(5)
        ).all()
        for schedule, location in schedules:
            if not any(source.id == location.content_id for source in sources):
                sources.append(
                    ChatSource(
                        type="FESTIVAL",
                        id=location.content_id,
                        title=location.title,
                        subtitle=f"{schedule.start_date} ~ {schedule.end_date}",
                        image_url=location.first_image,
                    )
                )
            context_lines.append(
                f"축제: {location.title} / 일정: {schedule.start_date}~{schedule.end_date} / 장소: {location.addr1}"
            )

    context_lines.insert(0, f"JSON 데이터 검색어: {', '.join(terms) if terms else '없음'}")
    return sources[:DB_SOURCE_LIMIT], context_lines


# ---------------------------------------------------------------------------
# RAG 근거
# ---------------------------------------------------------------------------

def _rag_label(hit: RagHit) -> str:
    parts = [hit.title]
    if hit.year:
        parts.append(f"{hit.year}년")
    if hit.collection in ("survey_report", "survey_stats") and hit.audience_label:
        parts.append(hit.audience_label)
    if hit.is_preliminary:
        parts.append("잠정치(확정 전 수치)")
    elif hit.status_label:
        parts.append(hit.status_label)
    if hit.location:
        parts.append(hit.location)
    return " · ".join(parts)


def _rag_source(hit: RagHit) -> ChatSource:
    meta = hit.meta
    if hit.collection == "event":
        period = f"{meta.get('start_date')} ~ {meta.get('end_date')}"
        return ChatSource(
            type="EVENT", id=hit.id, title=meta.get("name") or hit.title,
            subtitle=" · ".join(filter(None, [period, meta.get("district")])),
            image_url=meta.get("image_url") or "", url=meta.get("url") or "",
        )
    if hit.collection in ("place", "analytics"):
        return ChatSource(
            type="PLACE_INFO" if hit.collection == "place" else "DATA", id=hit.id,
            title=meta.get("name") or hit.title,
            subtitle=" · ".join(filter(None, [hit.title, meta.get("district")])),
            image_url=meta.get("image_url") or "", url=meta.get("url") or "",
        )
    return ChatSource(
        type="REPORT", id=hit.id, title=hit.title,
        subtitle=" · ".join(filter(None, [
            f"{hit.year}년" if hit.year else "", hit.audience_label, hit.status_label, hit.location,
        ])),
    )


def _rag_context(hits: list[RagHit]) -> tuple[list[ChatSource], list[str]]:
    sources: list[ChatSource] = []
    seen_docs: set[str] = set()
    lines: list[str] = []
    for number, hit in enumerate(hits, start=1):
        lines.append(f"[근거 R{number}] {_rag_label(hit)}\n{hit.text}")
        # 보고서는 문서 단위로 한 번만 출처에 노출한다(같은 보고서의 여러 페이지 중복 방지).
        dedupe_key = hit.doc_id if hit.collection in ("survey_report", "survey_stats") else hit.id
        if dedupe_key not in seen_docs and len(sources) < RAG_SOURCE_LIMIT:
            seen_docs.add(dedupe_key)
            sources.append(_rag_source(hit))
    return sources, lines


# ---------------------------------------------------------------------------
# 대화 기록 · 캐시 · 번역
# ---------------------------------------------------------------------------

def _normalize_history(history: list[dict], message: str) -> list[dict]:
    items = [
        {
            "role": "assistant" if item.get("role") == "assistant" else "user",
            "content": str(item.get("content") or "").strip(),
        }
        for item in history
    ]
    items = [item for item in items if item["content"]]
    # 프론트가 방금 보낸 질문을 history 끝에도 담아 보내면 같은 질문이 두 번 전달되므로 제거한다.
    if items and items[-1]["role"] == "user" and items[-1]["content"] == message.strip():
        items.pop()
    items = items[-HISTORY_LIMIT:]
    # 대화는 사용자 턴으로 시작해야 하므로 앞쪽 assistant 메시지(인사말 등)는 제외한다.
    while items and items[0]["role"] == "assistant":
        items.pop(0)
    for item in items:
        item["content"] = item["content"][:HISTORY_CHAR_LIMIT]
    return items


def _cache_key(message: str, history: list[dict], language: str) -> tuple:
    return (language, " ".join(message.split()), tuple((item["role"], item["content"]) for item in history))


async def _korean_search_query(message: str, language: str) -> str:
    if language == "ko" or not settings.gemini_api_key:
        return message
    key = (language, message)
    cached = translation_cache.get(key)
    if cached is not None:
        return cached
    try:
        translated = await generate_text(
            [{
                "role": "user",
                "parts": [{"text": (
                    "Translate the following Seoul travel search query into Korean. "
                    "Return only concise Korean search keywords with no explanation:\n" + message
                )}],
            }],
            max_output_tokens=256,
        ) or message
    except Exception as error:
        logger.info("검색어 번역 실패, 원문으로 검색합니다: %r", error)
        return message
    translation_cache.set(key, translated)
    return translated


def _fallback_answer(sources: list[ChatSource], language: str = "ko") -> str:
    if not sources:
        return FALLBACK_MESSAGES.get(language, FALLBACK_MESSAGES["ko"])

    titles = ", ".join(source.title for source in sources[:4])
    template = RESULT_MESSAGES.get(language, RESULT_MESSAGES["ko"])
    return template.format(titles=titles)


def _build_context(db_lines: list[str], rag_lines: list[str]) -> str:
    sections = []
    if db_lines:
        sections.append("[Soulrip DB 검색 결과]\n" + "\n".join(db_lines))
    if rag_lines:
        sections.append("[서울관광 실태조사·공공데이터 근거]\n" + "\n\n".join(rag_lines))
    context = "\n\n".join(sections)
    if len(context) > CONTEXT_CHAR_LIMIT:
        context = context[:CONTEXT_CHAR_LIMIT] + "\n…(이하 생략)"
    return context


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

async def answer_chat(db: Session, message: str, history: list[dict], language: str = "ko") -> ChatResponse:
    history = _normalize_history(history, message)
    key = _cache_key(message, history, language)
    cached = chat_cache.get(key)
    if cached is not None:
        return cached

    search_query = await _korean_search_query(message, language)
    # DB 검색(스레드)과 RAG 검색은 서로 독립적이므로 동시에 실행한다.
    (db_sources, db_lines), rag_hits = await asyncio.gather(
        to_thread.run_sync(_search_context, db, search_query),
        rag_service.search(search_query),
    )
    rag_sources, rag_lines = _rag_context(rag_hits)
    sources = db_sources + rag_sources
    fallback = _fallback_answer(sources, language)
    suggestions = SUGGESTIONS.get(language, SUGGESTIONS["ko"])

    if not settings.gemini_api_key:
        return ChatResponse(answer=fallback, sources=sources, suggestions=suggestions, used_ai=False)

    contents = [
        {"role": "model" if item["role"] == "assistant" else "user", "parts": [{"text": item["content"]}]}
        for item in history
    ]
    context = _build_context(db_lines, rag_lines)
    contents.append({
        "role": "user",
        "parts": [{"text": f"질문: {message}\n\n검색된 데이터:\n{context or '검색 결과 없음'}"}],
    })

    try:
        answer = await generate_text(
            contents,
            system_instruction=SYSTEM_PROMPT.format(language=LANGUAGE_NAMES.get(language, "Korean")),
        )
    except Exception as error:
        logger.warning("Gemini 호출 실패, fallback 응답을 반환합니다: %r", error)
        return ChatResponse(answer=fallback, sources=sources, suggestions=suggestions, used_ai=False)

    response = ChatResponse(answer=answer or fallback, sources=sources, suggestions=suggestions, used_ai=bool(answer))
    if answer:
        chat_cache.set(key, response)
    return response
