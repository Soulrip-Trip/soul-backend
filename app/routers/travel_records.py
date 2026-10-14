from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Location, TravelRecord, TravelRecordItem
from app.schemas.travel_record import (
    TravelRecordCreate,
    TravelRecordItemOut,
    TravelRecordListResponse,
    TravelRecordOut,
    TravelRecordUpdate,
)
from app.services.serializers import place_out

router = APIRouter(prefix="/travel-records", tags=["travel-records"])


def _record_items(db: Session, record_ids: list[int]) -> dict[int, list[tuple[TravelRecordItem, Location]]]:
    """여러 기록의 장소 목록을 JOIN 한 번으로 가져온다(기록마다 조회하는 N+1 방지)."""
    if not record_ids:
        return {}
    rows = db.execute(
        select(TravelRecordItem, Location)
        .join(Location, TravelRecordItem.location_id == Location.id)
        .where(TravelRecordItem.record_id.in_(record_ids))
        .order_by(TravelRecordItem.record_id.asc(), TravelRecordItem.stop_order.asc())
    ).all()
    items: dict[int, list[tuple[TravelRecordItem, Location]]] = {}
    for item, location in rows:
        items.setdefault(item.record_id, []).append((item, location))
    return items


def _record_out(
    db: Session,
    record: TravelRecord,
    rows: list[tuple[TravelRecordItem, Location]] | None = None,
) -> TravelRecordOut:
    if rows is None:
        rows = _record_items(db, [record.id]).get(record.id, [])
    return TravelRecordOut(
        id=record.id,
        client_id=record.client_id,
        title=record.title,
        memo=record.memo,
        visited_at=record.visited_at,
        is_public=record.is_public,
        items=[
            TravelRecordItemOut(
                id=item.id,
                stop_order=item.stop_order,
                note=item.note,
                place=place_out(location),
            )
            for item, location in rows
        ],
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _replace_items(db: Session, record: TravelRecord, items) -> None:
    for existing in list(record.items):
        db.delete(existing)
    db.flush()

    # 장소를 content_id IN (...) 한 번으로 조회한다.
    content_ids = {item.content_id for item in items}
    locations = {
        location.content_id: location
        for location in db.scalars(select(Location).where(Location.content_id.in_(content_ids)))
    } if content_ids else {}

    for index, item in enumerate(items, start=1):
        location = locations.get(item.content_id)
        if location is None:
            raise HTTPException(status_code=400, detail=f"장소 {item.content_id}를 찾을 수 없습니다.")
        db.add(
            TravelRecordItem(
                record_id=record.id,
                location_id=location.id,
                stop_order=index,
                note=item.note,
            )
        )


@router.get("", response_model=TravelRecordListResponse)
def list_records(
    client_id: str = Query(alias="clientId", min_length=1),
    db: Session = Depends(get_db),
) -> TravelRecordListResponse:
    records = db.scalars(
        select(TravelRecord)
        .where(TravelRecord.client_id == client_id)
        .order_by(TravelRecord.visited_at.desc(), TravelRecord.created_at.desc())
    ).all()
    record_items = _record_items(db, [record.id for record in records])
    return TravelRecordListResponse(
        items=[_record_out(db, record, record_items.get(record.id, [])) for record in records],
        total=len(records),
    )


@router.post("", response_model=TravelRecordOut, status_code=201)
def create_record(payload: TravelRecordCreate, db: Session = Depends(get_db)) -> TravelRecordOut:
    record = TravelRecord(
        client_id=payload.client_id,
        title=payload.title.strip(),
        memo=payload.memo,
        visited_at=payload.visited_at,
        is_public=payload.is_public,
    )
    db.add(record)
    db.flush()
    _replace_items(db, record, payload.items)
    db.commit()
    db.refresh(record)
    return _record_out(db, record)


@router.get("/{record_id}", response_model=TravelRecordOut)
def get_record(
    record_id: int,
    client_id: str = Query(alias="clientId", min_length=1),
    db: Session = Depends(get_db),
) -> TravelRecordOut:
    record = db.get(TravelRecord, record_id)
    if record is None or (not record.is_public and record.client_id != client_id):
        raise HTTPException(status_code=404, detail="여행 기록을 찾을 수 없습니다.")
    return _record_out(db, record)


@router.patch("/{record_id}", response_model=TravelRecordOut)
def update_record(
    record_id: int,
    payload: TravelRecordUpdate,
    db: Session = Depends(get_db),
) -> TravelRecordOut:
    record = db.get(TravelRecord, record_id)
    if record is None or record.client_id != payload.client_id:
        raise HTTPException(status_code=404, detail="여행 기록을 찾을 수 없습니다.")

    if payload.title is not None:
        record.title = payload.title.strip()
    if payload.memo is not None:
        record.memo = payload.memo
    if payload.visited_at is not None:
        record.visited_at = payload.visited_at
    if payload.is_public is not None:
        record.is_public = payload.is_public
    if payload.items is not None:
        _replace_items(db, record, payload.items)

    db.commit()
    db.refresh(record)
    return _record_out(db, record)


@router.delete("/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    client_id: str = Query(alias="clientId", min_length=1),
    db: Session = Depends(get_db),
) -> Response:
    record = db.get(TravelRecord, record_id)
    if record is None or record.client_id != client_id:
        raise HTTPException(status_code=404, detail="여행 기록을 찾을 수 없습니다.")
    db.delete(record)
    db.commit()
    return Response(status_code=204)
