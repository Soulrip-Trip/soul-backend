import re
from functools import lru_cache

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import FestivalSchedule, Location, Post
from app.schemas.chat import ChatResponse, ChatSource

settings = get_settings()

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
MAX_SOURCES = 8
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
    # 지시어("거기", "그 근처")뿐이고 지역이 없으면 이전 대화의 지역을 이어받는다.
    if not districts and not residual:
        districts = _history_districts(history)
        if districts:
            note = "지역은 이전 대화에서 이어받음"

    frequencies = _term_frequencies(db, all_terms)
    residual_terms = _usable_terms(residual, frequencies)
    fallback_terms = _usable_terms(all_terms, frequencies)

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


def _search_context(db: Session, message: str, history: list[dict] | None = None) -> tuple[list[ChatSource], str]:
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

    festival_ids = [item.id for item in locations if item.content_type_id == 15]
    schedules: dict[int, list[str]] = {}
    if festival_ids:
        for location_id, start, end in db.execute(
            select(FestivalSchedule.location_id, FestivalSchedule.start_date, FestivalSchedule.end_date)
            .where(FestivalSchedule.location_id.in_(festival_ids))
            .order_by(FestivalSchedule.start_date.asc())
        ):
            schedules.setdefault(location_id, []).append(f"{start}~{end}")

    sources: list[ChatSource] = []
    context_lines: list[str] = []

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
        # 원본 JSON의 modifiedtime은 행사 일정이 아니므로 일정은 FestivalSchedule만 근거로 한다.
        date_text = ""
        if item.content_type_id == 15:
            date_text = f" / 일정: {', '.join(schedules[item.id])}" if item.id in schedules else " / 일정: 저장된 데이터에 없음"
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
        scheduled = db.execute(
            select(FestivalSchedule, Location)
            .join(Location, FestivalSchedule.location_id == Location.id)
            .order_by(FestivalSchedule.start_date.asc())
            .limit(5)
        ).all()
        for schedule, location in scheduled:
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
    return sources[:MAX_SOURCES], "\n".join([search_note, *context_lines])


def _fallback_answer(message: str, sources: list[ChatSource], language: str = "ko") -> str:
    if not sources:
        return FALLBACK_MESSAGES.get(language, FALLBACK_MESSAGES["ko"])

    titles = ", ".join(source.title for source in sources[:4])
    template = RESULT_MESSAGES.get(language, RESULT_MESSAGES["ko"])
    return template.format(titles=titles)


def _openai_chat(messages: list[dict]) -> str:
    import httpx

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={"model": settings.openai_model, "messages": messages},
        timeout=30.0,
    )
    response.raise_for_status()
    choices = response.json().get("choices") or [{}]
    return (choices[0].get("message", {}).get("content") or "").strip()


@lru_cache(maxsize=256)
def _korean_search_query(message: str, language: str) -> str:
    if language == "ko" or not settings.openai_api_key:
        return message
    try:
        return _openai_chat([{
            "role": "user",
            "content": (
                "Translate the following Seoul travel search query into Korean. "
                "Return only concise Korean search keywords with no explanation:\n" + message
            ),
        }]) or message
    except Exception:
        return message


def build_chat_context(
    db: Session, message: str, language: str = "ko", history: list[dict] | None = None
) -> tuple[list[ChatSource], str]:
    return _search_context(db, _korean_search_query(message, language), history)


def _system_instruction(language: str) -> str:
    return (
        "너는 Soulrip 서울 여행 도우미다. 반드시 제공된 데이터 문맥만 근거로 답한다. 규칙은 다음과 같다. "
        "1) 사용자가 말한 지역·유형 조건에 맞는 장소만 제시하고, 조건에 맞는 장소가 문맥에 없으면 없다고 답한다. "
        "2) 영업시간·가격·입장료·행사 일정·날짜·소요 시간·이동 시간·예약 방법·시설 정보가 문맥에 없으면 추측하지 말고 "
        "'저장된 데이터에 정보가 없다'고 답한다. 시간표나 표를 요청받아도 문맥에 없는 시각과 날짜는 만들지 않고 '정보 없음'으로 적는다. "
        "3) 장소의 분위기·혼자 가기 좋음·조용함·안전·접근성·사진 명소 같은 특성은 문맥에 없으면 말하지 않는다. "
        "장소는 이름·유형·주소처럼 제공된 정보로만 소개한다. "
        "4) 문맥에 문의 전화번호가 있으면 그대로 알려준다. "
        "5) 검색 결과가 없으면 모른다고 답한다. "
        "6) 답변에 사용한 장소명은 제공된 표기를 그대로 쓴다. "
        f"Answer concisely in {LANGUAGE_NAMES.get(language, 'Korean')}."
    )


def answer_chat(db: Session, message: str, history: list[dict], language: str = "ko") -> ChatResponse:
    sources, context = build_chat_context(db, message, language, history)
    fallback = _fallback_answer(message, sources, language)

    if not settings.openai_api_key:
        return ChatResponse(
            answer=fallback,
            sources=sources,
            suggestions=["혼자 걷기 좋은 곳", "이번 달 축제", "종로구 문화시설"],
            used_ai=False,
        )

    try:
        messages = [{"role": "system", "content": _system_instruction(language)}]
        messages += [
            {
                "role": "assistant" if item.get("role") == "assistant" else "user",
                "content": str(item.get("content") or ""),
            }
            for item in history[-10:]
            if item.get("content")
        ]
        messages.append({
            "role": "user",
            "content": f"질문: {message}\n\n검색된 데이터:\n{context or '검색 결과 없음'}",
        })
        answer = _openai_chat(messages) or fallback
        used_ai = True
    except Exception:
        answer = fallback
        used_ai = False

    return ChatResponse(
        answer=answer,
        sources=sources,
        suggestions=["혼자 걷기 좋은 곳", "이번 달 축제", "종로구 문화시설"],
        used_ai=used_ai,
    )
