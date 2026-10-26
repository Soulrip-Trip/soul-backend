"""data/manifest.json 로더.

모든 원천 자료는 manifest에 연도·조사 대상·확정/잠정 여부·출처를 메타데이터로 가진다.
검색 결과(chunk)에 이 메타데이터가 그대로 실려 LLM이 2026 잠정치를 확정치처럼 말하는 문제를 줄인다.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

AUDIENCE_LABELS = {"domestic": "내국인", "foreign": "외국인", "all": "전체"}
STATUS_LABELS = {"confirmed": "확정치", "preliminary": "잠정치", "reference": "공공데이터"}
COLLECTION_LABELS = {
    "survey_report": "실태조사 보고서",
    "survey_stats": "실태조사 통계표",
    "place": "관광 장소",
    "event": "문화행사",
    "analytics": "관광지 방문 데이터",
}


@dataclass(frozen=True)
class SourceDocument:
    id: str
    path: str
    loader: str
    collection: str
    title: str
    index: bool = True
    year: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    audience: str = "all"
    status: str = "reference"
    publisher: str = ""
    published_at: str = ""
    sample_size: int | None = None
    source_url: str = ""
    exclude_reason: str = ""
    options: dict = field(default_factory=dict)

    def resolve(self, data_dir: Path) -> list[Path]:
        # "[보고서] ..." 같은 파일명의 대괄호는 glob 문법으로 해석하지 않는다.
        if "*" in self.path or "?" in self.path:
            return sorted(data_dir.glob(self.path))
        path = data_dir / self.path
        return [path] if path.exists() else []

    def base_meta(self) -> dict:
        return {
            "doc_id": self.id,
            "collection": self.collection,
            "title": self.title,
            "year": self.year,
            "year_from": self.year_from,
            "year_to": self.year_to,
            "audience": self.audience,
            "status": self.status,
            "publisher": self.publisher,
            "source_url": self.source_url,
        }


def load_manifest(data_dir: Path) -> list[SourceDocument]:
    path = data_dir / "manifest.json"
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    known = set(SourceDocument.__dataclass_fields__)
    documents = []
    for item in payload["documents"]:
        unknown = set(item) - known
        if unknown:
            raise ValueError(f"manifest 문서 {item.get('id')}에 알 수 없는 필드가 있습니다: {sorted(unknown)}")
        documents.append(SourceDocument(**item))

    ids = [document.id for document in documents]
    duplicated = {value for value in ids if ids.count(value) > 1}
    if duplicated:
        raise ValueError(f"manifest 문서 id가 중복되었습니다: {sorted(duplicated)}")
    return documents
