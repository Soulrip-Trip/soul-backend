from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Collection = Literal["survey_report", "survey_stats", "place", "event", "analytics"]


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SearchRequest(CamelModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    collections: list[Collection] | None = None
    max_chars_per_hit: int | None = Field(default=None, ge=100, le=3000)


class SearchHit(CamelModel):
    id: str
    doc_id: str
    collection: str
    collection_label: str
    title: str
    year: int | None
    year_from: int | None
    year_to: int | None
    audience: str | None
    audience_label: str
    status: str | None
    status_label: str
    publisher: str
    source_url: str
    location: str
    text: str
    score: float
    meta: dict


class SearchResponse(CamelModel):
    query: str
    hints: dict
    hits: list[SearchHit]
    dense: bool
    cached: bool
    took_ms: float


class HealthResponse(CamelModel):
    status: Literal["ok", "index_missing"]
    index: dict | None
    cache: dict
    detail: str | None = None
