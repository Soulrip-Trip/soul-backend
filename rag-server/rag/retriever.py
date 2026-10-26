"""하이브리드 검색기.

1) BM25(로컬 역색인)로 후보 점수를 계산한다. 외부 API 호출 없음.
2) 질의에서 연도·조사 대상·의도(실태조사/장소/행사)를 추출해 메타데이터 가중치를 곱한다.
3) (선택) dense 벡터가 있으면 BM25 순위와 RRF(Reciprocal Rank Fusion)로 합친다.
4) 같은 문서에서 너무 많은 chunk가 뽑히지 않도록 문서당 개수를 제한한다.

인덱스는 프로세스 시작 시 한 번만 메모리에 올리고, 검색 요청마다 파일을 다시 읽지 않는다.
"""

import math
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from rag.index import Bm25Arrays, load_index
from rag.manifest import AUDIENCE_LABELS, COLLECTION_LABELS, STATUS_LABELS
from rag.text import tokenize

K1 = 1.2
B = 0.75
RRF_K = 60
CANDIDATES = 200

YEAR_PATTERN = re.compile(r"(20(?:19|2\d))\s*년?")
MONTH_PATTERN = re.compile(r"(?<!\d)(1[0-2]|[1-9])\s*월")
FOREIGN_WORDS = ("외국인", "외래", "해외", "인바운드", "foreign", "international", "overseas")
DOMESTIC_WORDS = ("내국인", "국내 관광", "국내관광", "국내 여행", "국내여행", "국민", "domestic")
SURVEY_WORDS = (
    "실태조사", "조사", "관광객", "통계", "비율", "지출", "소비", "만족도", "재방문", "체류", "트렌드", "특징",
    "응답", "평균", "퍼센트", "%", "국적", "동행", "목적", "방문객", "추이", "변화", "비교", "패턴", "경향", "잠정",
)
PLACE_WORDS = ("추천", "코스", "가볼", "장소", "명소", "산책", "길", "거리", "박물관", "미술관", "일정", "도서관", "공원")
EVENT_WORDS = ("전시", "공연", "축제", "행사", "콘서트", "뮤지컬", "연극", "클래식", "국악", "체험", "페스티벌", "무용")
METHOD_WORDS = ("조사 방법", "조사방법", "표본", "조사 개요", "조사개요", "용어", "정의", "조사 기간", "조사기간", "응답자 수")

# 보고서와 사용자 질문의 표현 차이를 메우는 질의 확장(확장어는 가중치 0.5)
QUERY_SYNONYMS = {
    "소비": ("지출", "비용"),
    "지출": ("소비",),
    "돈": ("지출", "비용"),
    "특징": ("특성",),
    "혼행": ("혼자", "동행인"),
    "혼자": ("혼자 방문", "동행인"),
    "숙소": ("숙박",),
    "맛집": ("음식",),
    "만족": ("만족도",),
    "재방문": ("재방문율", "재방문 의향"),
    "인기": ("방문 장소", "방문지"),
}


@dataclass
class QueryHints:
    years: list[int] = field(default_factory=list)
    months: list[tuple[int, int]] = field(default_factory=list)  # (year, month)
    audience: str | None = None
    survey: bool = False
    place: bool = False
    event: bool = False
    method: bool = False

    def as_dict(self) -> dict:
        return {
            "years": self.years,
            "months": [f"{year}-{month:02d}" for year, month in self.months],
            "audience": self.audience,
            "intents": [name for name in ("survey", "place", "event", "method") if getattr(self, name)],
        }


def parse_hints(query: str, today: date | None = None) -> QueryHints:
    today = today or date.today()
    lowered = query.lower()
    years = sorted({int(year) for year in YEAR_PATTERN.findall(query)})
    if "올해" in query:
        years.append(today.year)
    if "작년" in query or "지난해" in query:
        years.append(today.year - 1)

    months: list[tuple[int, int]] = []
    if any(word in query for word in ("이번 달", "이번달", "이달")):
        months.append((today.year, today.month))
    if "다음 달" in query or "다음달" in query:
        months.append((today.year + today.month // 12, today.month % 12 + 1))
    for month in MONTH_PATTERN.findall(query):
        months.append((years[0] if len(years) == 1 else today.year, int(month)))

    audience = None
    if any(word in lowered for word in FOREIGN_WORDS):
        audience = "foreign"
    elif any(word in lowered for word in DOMESTIC_WORDS):
        audience = "domestic"
    return QueryHints(
        years=sorted(set(years)),
        months=sorted(set(months)),
        audience=audience,
        survey=any(word in lowered for word in SURVEY_WORDS) or bool(years and audience),
        place=any(word in lowered for word in PLACE_WORDS),
        event=any(word in lowered for word in EVENT_WORDS),
        method=any(word in query for word in METHOD_WORDS),
    )


class Retriever:
    def __init__(
        self,
        chunks: list[dict],
        bm25: Bm25Arrays,
        meta: dict,
        vectors: np.ndarray | None = None,
    ) -> None:
        self.chunks = chunks
        self.bm25 = bm25
        self.meta = meta
        self.vectors = vectors
        self._avg_len = bm25.avg_doc_len or 1.0
        self._norm = K1 * (1 - B + B * bm25.doc_len / self._avg_len)
        self._n = len(chunks)

        # 메타데이터 가중치 계산을 벡터화하기 위한 배열
        self._collection = np.array([chunk["collection"] for chunk in chunks])
        self._audience = np.array([chunk.get("audience") or "all" for chunk in chunks])
        self._year = np.array([chunk.get("year") or 0 for chunk in chunks], dtype=np.int16)
        self._year_from = np.array([chunk.get("year_from") or 0 for chunk in chunks], dtype=np.int16)
        self._year_to = np.array([chunk.get("year_to") or 0 for chunk in chunks], dtype=np.int16)
        self._status = np.array([chunk.get("status") or "" for chunk in chunks])
        self._overview = np.array([(chunk.get("meta") or {}).get("section") == "overview" for chunk in chunks])
        confirmed_years = self._year[(self._status == "confirmed") & (self._year > 0)]
        self._latest_confirmed_year = int(confirmed_years.max()) if len(confirmed_years) else 0
        self._event_start = np.array(
            [_ordinal((chunk.get("meta") or {}).get("start_date")) for chunk in chunks], dtype=np.int32
        )
        self._event_end = np.array(
            [_ordinal((chunk.get("meta") or {}).get("end_date")) for chunk in chunks], dtype=np.int32
        )

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, index_dir: Path) -> "Retriever":
        started = time.perf_counter()
        chunks, bm25, meta, vectors = load_index(index_dir)
        retriever = cls(chunks, bm25, meta, vectors)
        retriever.meta = {**meta, "load_seconds": round(time.perf_counter() - started, 3)}
        return retriever

    @property
    def has_dense(self) -> bool:
        return self.vectors is not None

    def info(self) -> dict:
        return {
            "chunks": self._n,
            "terms": len(self.bm25.vocab),
            "dense": self.has_dense,
            "built_at": self.meta.get("built_at"),
            "load_seconds": self.meta.get("load_seconds"),
            "collections": {
                name: int((self._collection == name).sum()) for name in sorted(set(self._collection.tolist()))
            },
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _query_terms(query: str) -> dict[str, float]:
        terms = {term: 1.0 for term in tokenize(query)}
        for word, expansions in QUERY_SYNONYMS.items():
            if word in query:
                for expansion in expansions:
                    for term in tokenize(expansion):
                        terms.setdefault(term, 0.5)
        return terms

    def _bm25_scores(self, query: str) -> np.ndarray:
        scores = np.zeros(self._n, dtype=np.float32)
        for term, term_weight in self._query_terms(query).items():
            term_id = self.bm25.vocab.get(term)
            if term_id is None:
                continue
            start, end = self.bm25.term_offsets[term_id], self.bm25.term_offsets[term_id + 1]
            ids = self.bm25.doc_ids[start:end]
            tf = self.bm25.tfs[start:end]
            df = end - start
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            scores[ids] += term_weight * idf * tf * (K1 + 1) / (tf + self._norm[ids])
        return scores

    def _metadata_weights(self, hints: QueryHints, today: date) -> np.ndarray:
        weights = np.ones(self._n, dtype=np.float32)
        survey_mask = np.isin(self._collection, ("survey_report", "survey_stats"))

        if hints.years:
            years = np.array(hints.years, dtype=np.int16)
            exact = np.isin(self._year, years)
            in_range = (self._year_from > 0) & np.any(
                (self._year_from[:, None] <= years) & (years <= self._year_to[:, None]), axis=1
            )
            other_year = survey_mask & (self._year > 0) & ~exact
            weights[exact] *= 1.5
            weights[in_range] *= 1.15
            weights[other_year] *= 0.5

        else:
            # 연도를 말하지 않으면 최신 확정치를 우선하고, 잠정치는 보조 근거로 둔다.
            weights[survey_mask & (self._year == self._latest_confirmed_year)] *= 1.1
            weights[self._status == "preliminary"] *= 0.85

        if not hints.method:
            weights[self._overview] *= 0.6  # 조사 개요·용어 정의 페이지는 방법론 질문에서만 우선

        if hints.audience:
            matched = self._audience == hints.audience
            mismatched = np.isin(self._audience, ("domestic", "foreign")) & ~matched
            weights[matched] *= 1.25
            weights[mismatched] *= 0.6

        if hints.survey:
            weights[self._collection == "survey_report"] *= 1.3
            weights[self._collection == "survey_stats"] *= 1.15
        elif hints.place or hints.event:
            # 장소·행사만 묻는 질문에서 실태조사 문서가 단어 우연 일치로 올라오지 않게 한다.
            weights[survey_mask] *= 0.4
        if hints.place:
            weights[self._collection == "place"] *= 1.2
        if hints.event:
            weights[self._collection == "event"] *= 1.3

        # "이번 달", "11월"처럼 기간을 말하면 그 기간과 겹치는 행사를 우선한다.
        if hints.months:
            is_event = self._event_end > 0
            overlap = np.zeros(self._n, dtype=bool)
            for year, month in hints.months:
                first = date(year, month, 1).toordinal()
                last = date(year + month // 12, month % 12 + 1, 1).toordinal() - 1
                overlap |= is_event & (self._event_start <= last) & (self._event_end >= first)
            weights[overlap] *= 1.6
            weights[is_event & ~overlap] *= 0.3

        # 이미 끝난 행사는 추천 근거로 쓰지 않는다(과거 연도를 명시한 질문 제외).
        if not (hints.years and max(hints.years) < today.year):
            expired = (self._event_end > 0) & (self._event_end < today.toordinal())
            weights[expired] = 0.0
        return weights

    def search(
        self,
        query: str,
        top_k: int = 4,
        collections: list[str] | None = None,
        query_vector: np.ndarray | None = None,
        max_chars: int = 700,
        max_per_doc: int = 2,
        min_relative_score: float = 0.3,
        today: date | None = None,
    ) -> dict:
        today = today or date.today()
        hints = parse_hints(query, today)
        weights = self._metadata_weights(hints, today)
        if collections:
            weights[~np.isin(self._collection, collections)] = 0.0
        scores = self._bm25_scores(query) * weights

        if query_vector is not None and self.vectors is not None:
            ranked = self._fuse(scores, weights, query_vector)
        else:
            candidate_count = min(CANDIDATES, self._n)
            if candidate_count == 0:
                return {"hints": hints.as_dict(), "hits": []}
            top = np.argpartition(-scores, candidate_count - 1)[:candidate_count]
            top = top[np.argsort(-scores[top])]
            top = top[scores[top] > 0]
            if len(top) == 0:
                return {"hints": hints.as_dict(), "hits": []}
            threshold = float(scores[top[0]]) * min_relative_score
            ranked = [(int(index), float(scores[index])) for index in top if scores[index] >= threshold]

        # 여러 연도를 비교하는 질문이면 연도별로 고르게 근거를 뽑는다.
        year_quota = math.ceil(top_k / len(hints.years)) if len(hints.years) >= 2 else top_k
        hits = []
        per_doc: dict[str, int] = {}
        per_year: dict[int, int] = {}
        for index, score in ranked:
            chunk = self.chunks[index]
            year = chunk.get("year") or 0
            if per_doc.get(chunk["doc_id"], 0) >= max_per_doc:
                continue
            if year and per_year.get(year, 0) >= year_quota:
                continue
            per_doc[chunk["doc_id"]] = per_doc.get(chunk["doc_id"], 0) + 1
            per_year[year] = per_year.get(year, 0) + 1
            hits.append(self._hit(chunk, score, max_chars))
            if len(hits) >= top_k:
                break
        return {"hints": hints.as_dict(), "hits": hits}

    def _fuse(self, scores: np.ndarray, weights: np.ndarray, query_vector: np.ndarray) -> list[tuple[int, float]]:
        assert self.vectors is not None
        dense = (self.vectors @ query_vector.astype(np.float32)) * weights
        dense[scores == 0] *= 0.5  # 키워드가 전혀 안 맞는 문서는 의미 유사도만으로 과대평가하지 않는다.
        dense[weights == 0] = -1.0  # 만료 행사·컬렉션 필터로 제외된 문서
        count = min(CANDIDATES, self._n)
        fused: dict[int, float] = {}
        for ranking in (scores, dense):
            order = np.argpartition(-ranking, count - 1)[:count]
            order = order[np.argsort(-ranking[order])]
            for rank, index in enumerate(order):
                if ranking[index] <= 0:
                    break
                fused[int(index)] = fused.get(int(index), 0.0) + 1.0 / (RRF_K + rank + 1)
        return sorted(fused.items(), key=lambda item: item[1], reverse=True)

    @staticmethod
    def _hit(chunk: dict, score: float, max_chars: int) -> dict:
        text = chunk["text"]
        if len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "…"
        return {
            "id": chunk["id"],
            "doc_id": chunk["doc_id"],
            "collection": chunk["collection"],
            "collection_label": COLLECTION_LABELS.get(chunk["collection"], chunk["collection"]),
            "title": chunk["title"],
            "year": chunk.get("year"),
            "year_from": chunk.get("year_from"),
            "year_to": chunk.get("year_to"),
            "audience": chunk.get("audience"),
            "audience_label": AUDIENCE_LABELS.get(chunk.get("audience") or "all", ""),
            "status": chunk.get("status"),
            "status_label": STATUS_LABELS.get(chunk.get("status") or "", ""),
            "publisher": chunk.get("publisher") or "",
            "source_url": chunk.get("source_url") or "",
            "location": chunk.get("location") or "",
            "text": text,
            "score": round(score, 4),
            "meta": chunk.get("meta") or {},
        }


def _ordinal(value: str | None) -> int:
    if not value:
        return 0
    try:
        return date.fromisoformat(value).toordinal()
    except ValueError:
        return 0


_lock = threading.Lock()
_cached: dict[str, Retriever] = {}


def get_retriever(index_dir: Path) -> Retriever:
    """프로세스당 한 번만 인덱스를 로드한다(스레드 안전)."""
    key = str(Path(index_dir).resolve())
    retriever = _cached.get(key)
    if retriever is not None:
        return retriever
    with _lock:
        if key not in _cached:
            _cached[key] = Retriever.load(Path(index_dir))
        return _cached[key]
