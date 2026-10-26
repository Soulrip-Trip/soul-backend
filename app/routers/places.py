import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Location
from app.schemas.common import PaginationMeta
from app.schemas.location import (
    NearbyPlaceOut,
    NearbyPlaceResponse,
    PlaceListResponse,
    PlaceMapResponse,
    PlaceOut,
)
from app.services.recommendation import haversine_km
from app.services.serializers import place_map_out, place_out

router = APIRouter(prefix="/places", tags=["places"])

KM_PER_DEGREE = 110.0


@router.get("", response_model=PlaceListResponse)
def list_places(
    q: str | None = None,
    content_type: list[str] | None = Query(default=None, alias="contentType"),
    district: str | None = None,
    has_image: bool | None = Query(default=None, alias="hasImage"),
    featured: bool | None = None,
    sort: Literal["latest", "name", "random"] = "latest",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PlaceListResponse:
    filters = []

    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Location.title.ilike(like),
                Location.addr1.ilike(like),
                Location.addr2.ilike(like),
                Location.content_type.ilike(like),
                Location.tags_json.ilike(like),
            )
        )
    if content_type:
        normalized = {value.strip() for value in content_type if value.strip()}
        filters.append(or_(Location.content_type.in_(normalized), Location.content_type_id.in_(normalized)))
    if district:
        filters.append(Location.district == district)
    if has_image is True:
        filters.append(Location.first_image != "")
    if has_image is False:
        filters.append(Location.first_image == "")
    if featured is not None:
        filters.append(Location.is_featured == featured)

    total = db.scalar(select(func.count()).select_from(Location).where(*filters)) or 0
    stmt = select(Location).where(*filters)
    if sort == "name":
        stmt = stmt.order_by(Location.title.asc())
    elif sort == "random":
        stmt = stmt.order_by(func.random())
    else:
        stmt = stmt.order_by(Location.source_modified_at.desc().nullslast(), Location.id.desc())

    items = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return PlaceListResponse(
        items=[place_out(item) for item in items],
        meta=PaginationMeta(total=total, page=page, size=size, pages=max(1, math.ceil(total / size))),
    )


@router.get("/map", response_model=PlaceMapResponse)
def map_places(
    content_type: list[str] | None = Query(default=None, alias="contentType"),
    district: str | None = None,
    q: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> PlaceMapResponse:
    filters = [
        Location.map_x.is_not(None),
        Location.map_y.is_not(None),
    ]
    if content_type:
        filters.append(Location.content_type.in_(content_type))
    if district:
        filters.append(Location.district == district)
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(Location.title.ilike(like), Location.addr1.ilike(like)))

    items = db.scalars(select(Location).where(*filters).limit(limit)).all()
    return PlaceMapResponse(items=[place_map_out(item) for item in items], total=len(items))


@router.get("/nearby", response_model=NearbyPlaceResponse)
def nearby_places(
    latitude: float,
    longitude: float,
    radius_km: float = Query(default=3.0, alias="radiusKm", gt=0, le=50),
    limit: int = Query(default=20, ge=1, le=100),
    content_type: list[str] | None = Query(default=None, alias="contentType"),
    db: Session = Depends(get_db),
) -> NearbyPlaceResponse:
    # 반경을 감싸는 위경도 사각형으로 먼저 거른 뒤 정확한 거리는 haversine으로 계산한다.
    # 위도 1도 ≈ 111km보다 작은 값(110km)으로 나눠 사각형이 원을 항상 포함하도록 한다.
    lat_delta = radius_km / KM_PER_DEGREE
    lng_delta = radius_km / (KM_PER_DEGREE * max(math.cos(math.radians(latitude)), 0.01))
    filters = [
        Location.map_x.is_not(None),
        Location.map_y.is_not(None),
        Location.map_y.between(latitude - lat_delta, latitude + lat_delta),
        Location.map_x.between(longitude - lng_delta, longitude + lng_delta),
    ]
    if content_type:
        filters.append(Location.content_type.in_(content_type))

    # 좌표 인덱스를 타면 반환 순서가 바뀌므로, 같은 거리일 때의 순서를 기존과 같이 id 순으로 고정한다.
    candidates = db.scalars(select(Location).where(*filters).order_by(Location.id.asc())).all()
    results: list[tuple[float, Location]] = []
    for item in candidates:
        distance = haversine_km(latitude, longitude, item.map_y, item.map_x)
        if distance <= radius_km:
            results.append((distance, item))

    results.sort(key=lambda value: value[0])
    response_items = [
        NearbyPlaceOut(**place_out(item).model_dump(), distance_km=round(distance, 3))
        for distance, item in results[:limit]
    ]
    return NearbyPlaceResponse(items=response_items, total=len(results))


@router.get("/{content_id}", response_model=PlaceOut)
def get_place(content_id: str, db: Session = Depends(get_db)) -> PlaceOut:
    item = db.scalar(select(Location).where(Location.content_id == content_id))
    if item is None:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다.")
    return place_out(item)
