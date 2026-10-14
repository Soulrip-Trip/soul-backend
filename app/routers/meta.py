from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import TTLCache
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import Location, Post

router = APIRouter(prefix="/meta", tags=["meta"])
settings = get_settings()

# 카테고리·자치구 집계는 시드 때만 바뀌므로 길게, 게시글 수가 포함된 stats는 짧게 캐시한다.
meta_cache = TTLCache("meta", maxsize=8, ttl=settings.meta_cache_ttl_seconds)
stats_cache = TTLCache("meta-stats", maxsize=1, ttl=min(30, settings.meta_cache_ttl_seconds))


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    def load():
        rows = db.execute(
            select(Location.content_type_id, Location.content_type, func.count(Location.id))
            .group_by(Location.content_type_id, Location.content_type)
            .order_by(Location.content_type_id.asc())
        ).all()
        return {
            "items": [
                {"contentTypeId": content_type_id, "name": content_type, "count": count}
                for content_type_id, content_type, count in rows
            ]
        }

    return meta_cache.get_or_set("categories", load)


@router.get("/districts")
def districts(db: Session = Depends(get_db)):
    def load():
        rows = db.execute(
            select(Location.district, func.count(Location.id))
            .where(Location.district.is_not(None))
            .group_by(Location.district)
            .order_by(Location.district.asc())
        ).all()
        return {"items": [{"district": district, "count": count} for district, count in rows]}

    return meta_cache.get_or_set("districts", load)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    def load():
        return {
            "places": db.scalar(select(func.count()).select_from(Location).where(Location.content_type_id.not_in([15, 25]))) or 0,
            "festivals": db.scalar(select(func.count()).select_from(Location).where(Location.content_type_id == 15)) or 0,
            "courses": db.scalar(select(func.count()).select_from(Location).where(Location.content_type_id == 25)) or 0,
            "posts": db.scalar(select(func.count()).select_from(Post)) or 0,
        }

    return stats_cache.get_or_set("stats", load)
