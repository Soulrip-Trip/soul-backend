from typing import Any

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class MessageResponse(CamelModel):
    message: str


class PaginationMeta(CamelModel):
    total: int
    page: int
    size: int
    pages: int


class HealthResponse(CamelModel):
    status: str
    app: str
    database: str
    rag: str = "off"


class ErrorResponse(CamelModel):
    detail: str | dict[str, Any]
