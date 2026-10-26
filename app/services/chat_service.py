"""지역 정보 챗봇.

흐름
1. 대화 기록 정규화(중복 질문·인사말 제거, 최근 10개, 메시지 길이 상한)
2. 응답 캐시 확인(같은 언어·질문·대화 맥락이면 OpenAI 재호출 없음)
3. 비한국어 질문은 한국어 검색어로 변환(캐시)
4. SQLite 장소·축제·게시글 검색과 RAG(실태조사·공공데이터) 검색을 asyncio.gather로 동시에 수행
5. 검색 결과만 근거로 OpenAI 호출, 실패하면 검색 결과 기반 fallback
"""

import asyncio
import logging
import re
from datetime import date

from anyio import to_thread
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.cache import TTLCache
from app.core.config import get_settings
from app.db.models import FestivalSchedule, Location, Post
from app.schemas.chat import ChatResponse, ChatSource
from app.services.openai_client import generate_text
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
    "너는 Soulrip 서울 혼행 여행 도우미다. 반드시 제공된 '검색된 데이터'만 근거로 답한다. 규칙은 다음과 같다.\n"
    "1) 사용자가 말한 지역·유형 조건에 맞는 장소만 제시하고, 조건에 맞는 장소가 데이터에 없으면 없다고 답한다.\n"
    "2) 영업시간·가격·입장료·행사 일정·날짜·소요 시간·이동 시간·예약 방법·시설 정보가 데이터에 없으면 추측하지 말고 "
    "'저장된 데이터에 정보가 없다'고 답한다. 시간표나 표를 요청받아도 데이터에 없는 시각과 날짜는 만들지 않고 '정보 없음'으로 적는다. "
    "'다음 달'·'이번 주말' 같은 상대 표현을 실제 연월일로 바꿔 말하지 않고, 실태조사의 평균 지출 같은 통계를 특정 장소의 입장료·가격처럼 제시하지 않는다.\n"
    "3) 장소의 분위기·혼자 가기 좋음·조용함·안전·접근성·사진 명소 같은 특성은 데이터에 없으면 말하지 않는다. "
    "장소는 이름·유형·주소처럼 제공된 정보로만 소개한다.\n"
    "4) 데이터에 문의 전화번호가 있으면 그대로 알려준다.\n"
    "5) 검색 결과가 없으면 모른다고 답한다.\n"
    "6) 답변에 사용한 장소명·행사명은 제공된 표기를 그대로 쓴다.\n"
    "7) 서울관광 실태조사 수치를 인용할 때는 연도와 조사 대상(내국인/외국인)을 함께 밝힌다. "
    "'잠정치'로 표시된 자료는 확정 전 수치이므로 잠정치임을 명시하고, 서로 다른 연도·조사 대상의 수치를 하나의 수치처럼 합치지 않는다. "
    "실태조사는 관광객 전체의 경향이므로 개인 일정 추천에 쓸 때는 '조사에 따르면'처럼 근거임을 드러낸다.\n"
    "Answer concisely in {language}."
)


def _system_instruction(language: str) -> str:
    return SYSTEM_PROMPT.format(language=LANGUAGE_NAMES.get(language, "Korean"))


# ---------------------------------------------------------------------------
# DB 검색
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "추천", "추천해줘", "추천해주세요", "알려줘", "알려주세요", "보여줘", "보여주세요", "어디", "어떤", "대해",
    "있는", "좋은", "가볼만한", "서울", "서울시", "장소", "정보", "관련",
    "시설", "근처", "주변", "가까운", "그럼", "거기", "거기서", "그곳", "같은",
}
PARTICLES = ("에서", "으로", "에게", "에는", "이랑", "하고", "까지", "부터", "의", "을", "를", "은", "는", "이", "가", "에", "도")

# 자치구와 영문 표기. 한글은 전체 이름, 어간(구 제외)은 뒤에 조사·공백이 올 때만 자치구로 본다.
# (예: "종로에서"는 자치구지만 "동대문디자인플라자"의 "동대문"은 장소명이다.)
SEOUL_DISTRICTS = {
    "강남구": ("gangnam",), "강동구": ("gangdong",), "강북구": ("gangbuk",), "강서구": ("gangseo",),
    "관악구": ("gwanak",), "광진구": ("gwangjin",), "구로구": ("guro",), "금천구": ("geumcheon",),
    "노원구": ("nowon",), "도봉구": ("dobong",), "동대문구": ("dongdaemun",), "동작구": ("dongjak",),
    "마포구": ("mapo",), "서대문구": ("seodaemun",), "서초구": ("seocho",), "성동구": ("seongdong",),
    "성북구": ("seongbuk",), "송파구": ("songpa",), "양천구": ("yangcheon",), "영등포구": ("yeongdeungpo",),
    "용산구": ("yongsan",), "은평구": ("eunpyeong",), "종로구": ("jongno",), "중구": ("jung-gu", "jung gu", "junggu"),
    "중랑구": ("jungnang",),
}
_STEM_FOLLOWER = r"(?=$|[^가-힣]|에서|에|의|쪽|지역|근처|으로|도|만|는|은|이|가|을|를|과|와)"
_DISTRICT_PATTERNS = {
    name: re.compile(re.escape(name[:-1]) + r"구?" + _STEM_FOLLOWER) if len(name) > 2 else re.compile(re.escape(name))
    for name in SEOUL_DISTRICTS
}

# content_type_id별 사용자 표현. 원본 content_type 값(관광지, 문화시설, ...)과 의미를 바꾸지 않는다.
CONTENT_TYPE_ALIASES = {
    12: ("관광지", "명소"),
    14: ("문화시설",),
    15: ("축제", "행사", "공연", "페스티벌"),
    28: ("레포츠", "스포츠"),
    32: ("숙박", "숙소", "호텔", "게스트하우스", "호스텔"),
    38: ("쇼핑",),
}
CONTENT_TYPE_NAMES = {12: "관광지", 14: "문화시설", 15: "축제공연행사", 28: "레포츠", 32: "숙박", 38: "쇼핑"}

CANDIDATE_LIMIT = 400  # 정렬 전에 후보를 자르는 개수. 너무 작으면 조건에 맞는 장소가 후보에서 밀린다.
GENERIC_TERM_ROWS = 600  # 이 이상 장소에 걸리는 단어는 변별력이 없어 검색어에서 제외한다.
MAX_TERMS = 10
MAX_SOURCES = DB_SOURCE_LIMIT
MAX_POST_SOURCES = 2
LOCATION_ORDER = (
    Location.is_featured.desc(),
    Location.solo_score.desc().nullslast(),
    Location.source_modified_at.desc(),
)


def _detect_districts(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for name, english in SEOUL_DISTRICTS.items():
        if _DISTRICT_PATTERNS[name].search(text) or any(word in lowered for word in english):
            found.append(name)
    return found


def _detect_content_types(text: str) -> list[int]:
    return [type_id for type_id, aliases in CONTENT_TYPE_ALIASES.items() if any(alias in text for alias in aliases)]


def _is_constraint_word(term: str) -> bool:
    """지역·유형을 가리키는 단어 자체인가. 장소명에 별칭이 포함된 경우(허준축제)는 제외한다."""
    if term in SEOUL_DISTRICTS or any(term == name[:-1] for name in SEOUL_DISTRICTS if len(name) > 2):
        return True
    return any(term in (alias, alias + "시설") for aliases in CONTENT_TYPE_ALIASES.values() for alias in aliases)


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
    return terms[:MAX_TERMS * 2]


def _term_condition(term: str):
    like = f"%{term}%"
    return or_(
        Location.title.ilike(like),
        Location.addr1.ilike(like),
        Location.addr2.ilike(like),
        Location.district.ilike(like),
        Location.content_type.ilike(like),
    )


def _term_frequencies(db: Session, terms: list[str]) -> dict[str, int]:
    """단어별로 몇 개의 장소에 걸리는지 한 번의 query로 센다."""
    if not terms:
        return {}
    row = db.execute(select(*[func.sum(case((_term_condition(term), 1), else_=0)) for term in terms])).one()
    return {term: int(count or 0) for term, count in zip(terms, row)}


def _usable_terms(terms: list[str], frequencies: dict[str, int]) -> list[str]:
    """DB에 실제로 있는 단어만 쓰고, 너무 흔한 단어는 뺀다. 전부 흔하면 가장 드문 하나만 남긴다."""
    alive = [term for term in terms if frequencies.get(term, 0) > 0]
    specific = [term for term in alive if frequencies[term] <= GENERIC_TERM_ROWS]
    return (specific or sorted(alive, key=frequencies.get)[:1])[:MAX_TERMS]


def _history_districts(history: list[dict] | None) -> list[str]:
    for turn in reversed((history or [])[-6:]):
        found = _detect_districts(str(turn.get("content") or ""))
        if found:
            return found
    return []


def _rank(candidates: list[Location], terms: list[str], frequencies: dict[str, int]) -> list[Location]:
    """드문 단어에 일치할수록, 제목과 거의 같을수록 앞에 둔다. (흔한 단어 하나에 걸린 장소가 위로 오지 않게 한다.)"""

    def relevance(item: Location) -> tuple[float, int, int]:
        title = item.title.lower()
        searchable = " ".join((item.title, item.addr1, item.addr2, item.district or "", item.content_type)).lower()
        score, matched = 0.0, 0
        for term in terms:
            needle = term.lower()
            if needle not in searchable:
                continue
            weight = 1 / max(frequencies.get(term, 1), 1)
            matched += 1
            score += weight
            if needle in title:
                score += weight
                if len(needle) >= len(title) - 1:  # 제목과 사실상 같은 장소명
                    score += 1
        return score, matched, item.is_featured

    return sorted(candidates, key=relevance, reverse=True)


def _search_locations(
    db: Session, message: str, history: list[dict] | None
) -> tuple[list[Location], list[str], list[str], list[int], str]:
    """(장소, 사용한 검색어, 적용한 지역, 적용한 유형 id, 검색 메모)를 돌려준다."""
    all_terms = _search_terms(message)
    districts = _detect_districts(message)
    type_ids = _detect_content_types(message)
    residual = [term for term in all_terms if not _is_constraint_word(term)]

    note = ""
    frequencies = _term_frequencies(db, all_terms)
    residual_terms = _usable_terms(residual, frequencies)
    fallback_terms = _usable_terms(all_terms, frequencies)

    # 지시어("거기", "그 근처")나 DB에 없는 군더더기 단어("있나요")뿐이고 지역이 없으면 이전 대화의 지역을 이어받는다.
    if not districts and not residual_terms:
        districts = _history_districts(history)
        if districts:
            note = "지역은 이전 대화에서 이어받음"

    def fetch(*where) -> list[Location]:
        return list(db.scalars(select(Location).where(*where).order_by(*LOCATION_ORDER).limit(CANDIDATE_LIMIT)))

    constraints = []
    if districts:
        constraints.append(Location.district.in_(districts))
    if type_ids:
        constraints.append(Location.content_type_id.in_(type_ids))

    candidates: list[Location] = []
    rank_terms = residual_terms
    if constraints:
        if residual_terms:
            candidates = fetch(*constraints, or_(*[_term_condition(term) for term in residual_terms]))
        if not candidates:
            candidates = fetch(*constraints)
        if not candidates:
            note = "조건에 맞는 장소가 없어 조건을 완화해 검색함"
            districts, type_ids = [], []
    if not candidates and fallback_terms:
        candidates = fetch(or_(*[_term_condition(term) for term in fallback_terms]))
        rank_terms = fallback_terms
    return _rank(candidates, rank_terms, frequencies)[:MAX_SOURCES], all_terms, districts, type_ids, note


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


def _search_context(
    db: Session, message: str, history: list[dict] | None = None
) -> tuple[list[ChatSource], list[str]]:
    locations, terms, districts, type_ids, note = _search_locations(db, message, history)
    if not locations and any(word in message for word in ("추천", "가볼", "혼자", "갈만한")):
        locations = db.scalars(
            select(Location)
            .where(Location.content_type_id.not_in((15, 25)))
            .order_by(*LOCATION_ORDER)
            .limit(MAX_SOURCES)
        ).all()

    posts: list[Post] = []
    if terms:
        post_filters = []
        for term in terms:
            like = f"%{term}%"
            post_filters.extend((Post.title.ilike(like), Post.content.ilike(like), Post.tags_json.ilike(like)))
        candidates = db.scalars(select(Post).where(or_(*post_filters)).order_by(Post.created_at.desc()).limit(20)).all()

        def matched(post: Post) -> int:
            text = f"{post.title} {post.content} {post.tags_json}".lower()
            return sum(term.lower() in text for term in terms)

        # 일반 단어 하나에 우연히 걸린 글은 제외한다. (단어가 하나뿐인 질문만 1개 일치를 허용)
        min_match = 1 if len(terms) <= 1 else 2
        posts = [post for post in sorted(candidates, key=matched, reverse=True) if matched(post) >= min_match][:MAX_POST_SOURCES]
    locations = locations[: MAX_SOURCES - len(posts)]  # 장소가 많아도 커뮤니티 글 자리를 보장한다.

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

    conditions = []
    if districts:
        conditions.append(f"지역={'/'.join(districts)}")
    if type_ids:
        conditions.append(f"유형={'/'.join(CONTENT_TYPE_NAMES[type_id] for type_id in type_ids)}")
    search_note = f"JSON 데이터 검색어: {', '.join(terms) if terms else '없음'}"
    if conditions:
        search_note += f" / 적용한 조건: {', '.join(conditions)}"
    if note:
        search_note += f" / 참고: {note}"
    context_lines.insert(0, search_note)
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
    if language == "ko" or not settings.openai_api_key:
        return message
    key = (language, message)
    cached = translation_cache.get(key)
    if cached is not None:
        return cached
    try:
        translated = await generate_text(
            [{
                "role": "user",
                "content": (
                    "Translate the following Seoul travel search query into Korean. "
                    "Return only concise Korean search keywords with no explanation:\n" + message
                ),
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

async def _gather_context(
    db: Session, message: str, history: list[dict], language: str
) -> tuple[list[ChatSource], list[str], list[str]]:
    """(출처, DB 검색 줄, RAG 근거 줄). history는 정규화된 대화 기록이다."""
    search_query = await _korean_search_query(message, language)
    # DB 검색(스레드)과 RAG 검색은 서로 독립적이므로 동시에 실행한다.
    (db_sources, db_lines), rag_hits = await asyncio.gather(
        to_thread.run_sync(_search_context, db, search_query, history),
        rag_service.search(search_query),
    )
    rag_sources, rag_lines = _rag_context(rag_hits)
    return db_sources + rag_sources, db_lines, rag_lines


async def build_chat_context(
    db: Session, message: str, language: str = "ko", history: list[dict] | None = None
) -> tuple[list[ChatSource], str]:
    """answer_chat이 LLM에 넘기는 것과 같은 출처·컨텍스트를 만든다. (평가 하네스가 사용)"""
    sources, db_lines, rag_lines = await _gather_context(db, message, _normalize_history(history or [], message), language)
    return sources, _build_context(db_lines, rag_lines)


async def answer_chat(db: Session, message: str, history: list[dict], language: str = "ko") -> ChatResponse:
    history = _normalize_history(history, message)
    key = _cache_key(message, history, language)
    cached = chat_cache.get(key)
    if cached is not None:
        return cached

    sources, db_lines, rag_lines = await _gather_context(db, message, history, language)
    fallback = _fallback_answer(sources, language)
    suggestions = SUGGESTIONS.get(language, SUGGESTIONS["ko"])

    if not settings.openai_api_key:
        return ChatResponse(answer=fallback, sources=sources, suggestions=suggestions, used_ai=False)

    messages = [{"role": item["role"], "content": item["content"]} for item in history]
    context = _build_context(db_lines, rag_lines)
    messages.append({"role": "user", "content": f"질문: {message}\n\n검색된 데이터:\n{context or '검색 결과 없음'}"})

    try:
        answer = await generate_text(messages, system_instruction=_system_instruction(language))
    except Exception as error:
        logger.warning("OpenAI 호출 실패, fallback 응답을 반환합니다: %r", error)
        return ChatResponse(answer=fallback, sources=sources, suggestions=suggestions, used_ai=False)

    response = ChatResponse(answer=answer or fallback, sources=sources, suggestions=suggestions, used_ai=bool(answer))
    if answer:
        chat_cache.set(key, response)
    return response
