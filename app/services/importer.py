import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FestivalSchedule, Location

CONTENT_FILES = {
    "서울_관광지.json": (12, "관광지"),
    "서울_문화시설.json": (14, "문화시설"),
    "서울_축제공연행사.json": (15, "축제공연행사"),
    "서울_여행코스.json": (25, "여행코스"),
    "서울_레포츠.json": (28, "레포츠"),
    "서울_숙박.json": (32, "숙박"),
    "서울_쇼핑.json": (38, "쇼핑"),
    "서울_음식점.json": (39, "음식점"),
}


def _empty_to_none(value):
    if value in (None, ""):
        return None
    return value


def _to_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _to_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _parse_source_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _district_from_address(address: str) -> str | None:
    match = re.search(r"서울특별시\s+([^\s]+구)", address or "")
    return match.group(1) if match else None


def _https_url(value: str) -> str:
    if value.startswith("http://"):
        return "https://" + value[len("http://"):]
    return value


def import_locations(db: Session, data_dir: Path) -> dict[str, int]:
    imported = 0
    updated = 0
    skipped_files = 0
    # 항목마다 SELECT 하지 않도록 기존 장소를 content_id 기준으로 한 번에 읽어 둔다.
    existing = {location.content_id: location for location in db.scalars(select(Location))}

    for filename, (default_type_id, default_type_name) in CONTENT_FILES.items():
        path = data_dir / filename
        if not path.exists():
            skipped_files += 1
            continue

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        content_type_name = payload.get("contentType") or default_type_name
        content_type_id = int(payload.get("contentTypeId") or default_type_id)
        region = payload.get("region") or "서울"

        for item in payload.get("items", []):
            content_id = str(item.get("contentid") or "").strip()
            title = str(item.get("title") or "").strip()
            if not content_id or not title:
                continue

            location = existing.get(content_id)
            is_new = location is None
            if is_new:
                location = Location(content_id=content_id)
                db.add(location)
                existing[content_id] = location

            location.content_type_id = int(item.get("contenttypeid") or content_type_id)
            location.content_type = content_type_name
            location.region = region
            location.title = title
            location.addr1 = item.get("addr1") or ""
            location.addr2 = item.get("addr2") or ""
            location.district = _district_from_address(location.addr1)
            location.zipcode = item.get("zipcode") or ""
            location.tel = item.get("tel") or ""
            location.map_x = _to_float(item.get("mapx"))
            location.map_y = _to_float(item.get("mapy"))
            location.map_level = _to_int(item.get("mlevel"))
            location.first_image = _https_url(item.get("firstimage") or "")
            location.first_image2 = _https_url(item.get("firstimage2") or "")
            location.copyright_type = item.get("cpyrhtDivCd") or ""
            location.area_code = item.get("areacode") or ""
            location.sigungu_code = item.get("sigungucode") or ""
            location.legal_region_code = item.get("lDongRegnCd") or ""
            location.legal_sigungu_code = item.get("lDongSignguCd") or ""
            location.cat1 = item.get("cat1") or ""
            location.cat2 = item.get("cat2") or ""
            location.cat3 = item.get("cat3") or ""
            location.lcls1 = item.get("lclsSystm1") or ""
            location.lcls2 = item.get("lclsSystm2") or ""
            location.lcls3 = item.get("lclsSystm3") or ""
            location.source_created_at = _parse_source_datetime(item.get("createdtime"))
            location.source_modified_at = _parse_source_datetime(item.get("modifiedtime"))

            if is_new:
                imported += 1
            else:
                updated += 1

        db.commit()

    return {"imported": imported, "updated": updated, "skippedFiles": skipped_files}


def import_festival_schedules(db: Session, data_dir: Path) -> dict[str, int]:
    path = data_dir / "festival_schedules.json"
    if not path.exists():
        return {"imported": 0, "skipped": 0}

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    imported = 0
    skipped = 0
    location_ids = dict(db.execute(select(Location.content_id, Location.id)).all())
    existing = set(db.execute(
        select(FestivalSchedule.location_id, FestivalSchedule.start_date, FestivalSchedule.end_date)
    ).all())
    for item in payload:
        content_id = str(item.get("contentId") or "")
        location_id = location_ids.get(content_id)
        if location_id is None:
            skipped += 1
            continue

        try:
            start_date = datetime.strptime(item["startDate"], "%Y-%m-%d").date()
            end_date = datetime.strptime(item.get("endDate") or item["startDate"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            skipped += 1
            continue

        key = (location_id, start_date, end_date)
        if key in existing:
            continue
        existing.add(key)

        db.add(
            FestivalSchedule(
                location_id=location_id,
                start_date=start_date,
                end_date=end_date,
                category=item.get("category"),
                description=item.get("description"),
                source=item.get("source") or "manual",
            )
        )
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped}
