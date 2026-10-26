import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import CourseStop, Location
from app.schemas.common import PaginationMeta
from app.schemas.course import (
    CourseListResponse,
    CourseOut,
    CourseRecommendRequest,
    GeneratedCourseOut,
)
from app.services.recommendation import order_nearest
from app.services.serializers import place_out

router = APIRouter(prefix="/courses", tags=["courses"])


def _course_stops(db: Session, course_ids: list[int]) -> dict[int, list[Location]]:
    """여러 코스의 경유지를 JOIN 한 번으로 가져온다(코스마다 조회하는 N+1 방지)."""
    if not course_ids:
        return {}
    rows = db.execute(
        select(CourseStop.course_location_id, Location)
        .join(Location, CourseStop.place_location_id == Location.id)
        .where(CourseStop.course_location_id.in_(course_ids))
        .order_by(CourseStop.course_location_id.asc(), CourseStop.stop_order.asc())
    ).all()
    stops: dict[int, list[Location]] = {}
    for course_id, location in rows:
        stops.setdefault(course_id, []).append(location)
    return stops


def _course_out(db: Session, course: Location, stops: list[Location] | None = None) -> CourseOut:
    if stops is None:
        stops = _course_stops(db, [course.id]).get(course.id, [])
    return CourseOut(
        id=course.id,
        content_id=course.content_id,
        title=course.title,
        image_url=course.first_image,
        district=course.district,
        longitude=course.map_x,
        latitude=course.map_y,
        description=course.description or "",
        stops=[place_out(location) for location in stops],
    )


@router.get("", response_model=CourseListResponse)
def list_courses(
    q: str | None = None,
    district: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> CourseListResponse:
    filters = [Location.content_type_id == 25]
    if q:
        filters.append(Location.title.ilike(f"%{q.strip()}%"))
    if district:
        filters.append(Location.district == district)

    total = db.scalar(select(func.count()).select_from(Location).where(*filters)) or 0
    courses = db.scalars(
        select(Location)
        .where(*filters)
        .order_by(Location.source_modified_at.desc().nullslast())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    stops = _course_stops(db, [course.id for course in courses])
    return CourseListResponse(
        items=[_course_out(db, course, stops.get(course.id, [])) for course in courses],
        meta=PaginationMeta(total=total, page=page, size=size, pages=max(1, math.ceil(total / size))),
    )


@router.post("/recommend", response_model=GeneratedCourseOut)
def recommend_course(
    payload: CourseRecommendRequest,
    db: Session = Depends(get_db),
) -> GeneratedCourseOut:
    filters = [
        Location.content_type_id.not_in([15, 25, 32]),
        Location.map_x.is_not(None),
        Location.map_y.is_not(None),
        Location.first_image != "",
    ]
    if payload.content_types:
        filters.append(Location.content_type.in_(payload.content_types))
    if payload.district:
        filters.append(Location.district == payload.district)

    candidates = db.scalars(
        select(Location)
        .where(*filters)
        .order_by(Location.is_featured.desc(), Location.solo_score.desc().nullslast(), func.random())
        .limit(80)
    ).all()
    if len(candidates) < 2:
        raise HTTPException(status_code=404, detail="추천 코스를 만들 장소가 충분하지 않습니다.")

    max_stops = payload.max_stops or max(2, min(6, round(payload.duration_hours / 1.2)))
    selected = candidates[: max_stops * 3]
    ordered = order_nearest(selected, payload.start_latitude, payload.start_longitude)[:max_stops]
    estimated_hours = round(max(2.0, len(ordered) * 1.2), 1)

    mood_text = f"{payload.mood} 분위기의 " if payload.mood else ""
    district_text = f"{payload.district} 중심 " if payload.district else "서울 "
    return GeneratedCourseOut(
        title=f"{district_text}{mood_text}혼행 코스",
        summary=f"이동 동선을 줄여 {len(ordered)}곳을 순서대로 둘러보는 추천 코스예요.",
        estimated_hours=estimated_hours,
        transport=payload.transport,
        stops=[place_out(item) for item in ordered],
    )


@router.get("/{content_id}", response_model=CourseOut)
def get_course(content_id: str, db: Session = Depends(get_db)) -> CourseOut:
    course = db.scalar(
        select(Location).where(Location.content_id == content_id, Location.content_type_id == 25)
    )
    if course is None:
        raise HTTPException(status_code=404, detail="여행 코스를 찾을 수 없습니다.")
    return _course_out(db, course)
