"""LLM 없이 결정적으로 계산하는 평가 지표.

모든 evaluator는 (inputs, outputs, reference_outputs)를 받아 {"key", "score", "comment"}를 돌려준다.
해당 질문에 적용되지 않는 지표는 score=None으로 돌려 평균에서 제외한다.
"""
import re

from scripts.chat_eval.dataset import as_list

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_NAME = r"(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE_PATTERNS = (
    re.compile(r"(?P<y>\d{4})\s*[-./년年]\s*(?P<m>\d{1,2})\s*[-./월月]\s*(?P<d>\d{1,2})"),
    re.compile(r"(?P<y>\d{4})\s*[년年]\s*(?P<m>\d{1,2})\s*[월月](?!\s*\d)"),
    re.compile(r"(?<!\d)(?P<m>\d{1,2})\s*[월月]\s*(?P<d>\d{1,2})\s*[일日]"),
    re.compile(_MONTH_NAME + r"\.?\s+(?P<d>\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MONTH_NAME),
)

_PRICE_PATTERNS = (
    re.compile(r"\d[\d,.]*\s*(?:만\s*)?원"),
    re.compile(r"[₩$]\s*\d[\d,.]*"),
    re.compile(r"\d[\d,.]*\s*(?:KRW|USD|won|dollars?|円|元)", re.IGNORECASE),
)
_HOURS_PATTERNS = (
    re.compile(r"(?<!\d)\d{1,2}\s*:\s*\d{2}(?!\d)"),
    re.compile(r"(?:오전|오후)\s*\d{1,2}\s*시"),
    re.compile(r"\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?(?=\s*(?:부터|~|-|까지))"),
    re.compile(r"(?<!\d)\d{1,2}\s*(?:a\.?m\.?|p\.?m\.?)(?![a-z])", re.IGNORECASE),
    re.compile(r"(?:午前|午後)\s*\d{1,2}\s*時|\d{1,2}\s*時"),
    re.compile(r"[월화수목금토일]요일\s*(?:은\s*)?(?:휴무|휴관|정기\s*휴)"),
    re.compile(r"closed\s+on\s+\w+", re.IGNORECASE),
)


def _result(key: str, score: float | None, comment: str = "") -> dict:
    return {"key": key, "score": score, "comment": comment}


def _skipped(key: str) -> dict:
    return _result(key, None, "OpenAI 호출 실패(fallback 답변)라 제외")


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _date_tuples(text: str) -> list[tuple[str, int | None, int | None, int | None]]:
    """텍스트에서 (원문, 연, 월, 일) 날짜 표현을 모두 뽑는다."""
    found = []
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groupdict()
            month = int(groups["m"]) if groups.get("m") else _MONTHS[groups["mon"][:3].lower()]
            day = int(groups["d"]) if groups.get("d") else None
            year = int(groups["y"]) if groups.get("y") else None
            found.append((match.group(0), year, month, day))
    return found


def source_hit(outputs: dict, reference_outputs: dict) -> dict:
    """기대한 장소/게시글이 검색 결과(sources)에 들어왔는가. (검색 재현율)"""
    sources = outputs["sources"]
    location_ids = {s["id"] for s in sources if s["type"] != "POST"}
    post_ids = {s["id"] for s in sources if s["type"] == "POST"}

    scores, notes = [], []
    if expected := reference_outputs.get("expected_content_ids"):
        hit = [cid for cid in expected if cid in location_ids]
        scores.append(len(hit) / len(expected))
        notes.append(f"장소 {len(hit)}/{len(expected)}")
    if expected := reference_outputs.get("expected_any_content_ids"):
        scores.append(float(any(cid in location_ids for cid in expected)))
        notes.append("장소(any) " + ("적중" if scores[-1] else "미적중"))
    if expected := reference_outputs.get("expected_post_ids"):
        hit = [pid for pid in expected if pid in post_ids]
        scores.append(len(hit) / len(expected))
        notes.append(f"게시글 {len(hit)}/{len(expected)}")

    if not scores:
        return _result("source_hit", None, "기대 출처 없음")
    return _result("source_hit", sum(scores) / len(scores), ", ".join(notes))


def source_condition_rate(outputs: dict, reference_outputs: dict) -> dict:
    """검색된 장소 중 질문의 지역·유형 조건을 만족하는 비율. (검색 기준 조건 충족률)"""
    constraints = reference_outputs.get("constraints")
    if not constraints:
        return _result("source_condition_rate", None, "조건 없음")

    locations = outputs["source_locations"]
    if not locations:
        return _result("source_condition_rate", 0.0, "검색된 장소 없음")

    def satisfies(location: dict) -> bool:
        return all(location.get(field) in as_list(allowed) for field, allowed in constraints.items())

    violated = [f"{l['title']}({l['district']}/{l['content_type']})" for l in locations if not satisfies(l)]
    rate = 1 - len(violated) / len(locations)
    return _result("source_condition_rate", rate, f"조건 {constraints} / 위반: {', '.join(violated[:5]) or '없음'}")


def must_include(outputs: dict, reference_outputs: dict) -> dict:
    needles = reference_outputs.get("must_include_any")
    if not needles:
        return _result("must_include", None, "필수 키워드 없음")
    if not outputs.get("used_ai"):
        return _skipped("must_include")
    answer = outputs["answer"].lower()
    hit = [needle for needle in needles if needle.lower() in answer]
    return _result("must_include", float(bool(hit)), f"기대 키워드(any) {needles} / 포함 {hit}")


def no_unsupported_date(inputs: dict, outputs: dict) -> dict:
    """답변의 날짜가 FestivalSchedule(실제 일정), RAG 행사 근거, 질문 중 하나에 근거한 것인가.

    원본 JSON의 modifiedtime은 행사 일정이 아니므로, Soulrip DB 검색 줄에 날짜가 있어도 근거로 인정하지 않는다.
    RAG(서울시 공공데이터)의 행사 근거에 적힌 날짜는 실제 출처가 있으므로 인정한다.
    """
    if not outputs.get("used_ai"):
        return _skipped("no_unsupported_date")
    allowed = []
    for iso in outputs.get("schedule_dates", []):
        year, month, day = (int(part) for part in iso.split("-"))
        allowed.append((year, month, day))
    allowed += [(year, month, day) for _, year, month, day in _date_tuples(outputs.get("rag_context", ""))]
    question = inputs["message"]

    unsupported = []
    for raw, year, month, day in _date_tuples(outputs["answer"]):
        if raw in question:
            continue
        supported = any(
            (year is None or ay is None or year == ay)
            and month == am
            and (day is None or (ad is not None and day == ad))
            for ay, am, ad in allowed
        )
        if not supported:
            unsupported.append(raw)
    return _result(
        "no_unsupported_date",
        float(not unsupported),
        f"근거 없는 날짜: {unsupported}" if unsupported else "근거 없는 날짜 없음",
    )


def no_unsupported_price_hours(inputs: dict, outputs: dict) -> dict:
    """답변의 가격·시각·휴무 표현이 검색 컨텍스트나 질문에 실제로 있는가."""
    if not outputs.get("used_ai"):
        return _skipped("no_unsupported_price_hours")
    evidence = _squash(outputs["context"] + "\n" + inputs["message"])
    unsupported = []
    for pattern in (*_PRICE_PATTERNS, *_HOURS_PATTERNS):
        for match in pattern.finditer(outputs["answer"]):
            if _squash(match.group(0)) not in evidence:
                unsupported.append(match.group(0))
    return _result(
        "no_unsupported_price_hours",
        float(not unsupported),
        f"근거 없는 가격/시각: {unsupported}" if unsupported else "근거 없는 가격/시각 없음",
    )


def language_match(inputs: dict, outputs: dict) -> dict:
    """요청 언어로 답했는지 거칠게 확인한다. (장소명은 한글 표기를 유지하므로 한글 포함 자체는 허용)"""
    if not outputs.get("used_ai"):
        return _skipped("language_match")
    language, answer = inputs.get("language", "ko"), outputs["answer"]
    hangul = len(re.findall(r"[가-힣]", answer))
    kana = len(re.findall(r"[぀-ヿ]", answer))
    han = len(re.findall(r"[一-鿿]", answer))
    latin = len(re.findall(r"[A-Za-z]", answer))

    if language == "ko":
        ok = hangul > 0
    elif language == "ja":
        ok = kana > 0
    elif language == "zh":
        ok = han > 0 and kana == 0
    else:
        ok = latin > hangul
    return _result("language_match", float(ok), f"language={language} hangul={hangul} kana={kana} han={han} latin={latin}")


def used_ai(outputs: dict) -> dict:
    """OpenAI 호출이 성공했는지. 0이면 fallback 답변이므로 답변 품질 지표를 해석하면 안 된다."""
    return _result("used_ai", float(bool(outputs.get("used_ai"))), f"attempts={outputs.get('attempts')}")


RETRIEVAL_EVALUATORS = (source_hit, source_condition_rate)
ANSWER_EVALUATORS = (used_ai, must_include, no_unsupported_date, no_unsupported_price_hours, language_match)
