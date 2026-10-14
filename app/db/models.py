from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        # 유형별 목록 + 최신순 정렬(places, courses, festivals 목록)
        Index("ix_locations_type_modified", "content_type_id", "source_modified_at"),
        # 주변 장소 검색의 위도·경도 범위(bounding box) 필터
        Index("ix_locations_coords", "map_y", "map_x"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    content_type_id: Mapped[int] = mapped_column(Integer, index=True)
    content_type: Mapped[str] = mapped_column(String(32), index=True)
    region: Mapped[str] = mapped_column(String(32), default="서울")

    title: Mapped[str] = mapped_column(String(255), index=True)
    addr1: Mapped[str] = mapped_column(String(500), default="")
    addr2: Mapped[str] = mapped_column(String(500), default="")
    district: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    zipcode: Mapped[str] = mapped_column(String(20), default="")
    tel: Mapped[str] = mapped_column(String(100), default="")

    map_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_level: Mapped[int | None] = mapped_column(Integer, nullable=True)

    first_image: Mapped[str] = mapped_column(Text, default="")
    first_image2: Mapped[str] = mapped_column(Text, default="")
    copyright_type: Mapped[str] = mapped_column(String(30), default="")

    area_code: Mapped[str] = mapped_column(String(20), default="")
    sigungu_code: Mapped[str] = mapped_column(String(20), default="")
    legal_region_code: Mapped[str] = mapped_column(String(20), default="")
    legal_sigungu_code: Mapped[str] = mapped_column(String(20), default="")

    cat1: Mapped[str] = mapped_column(String(50), default="")
    cat2: Mapped[str] = mapped_column(String(50), default="")
    cat3: Mapped[str] = mapped_column(String(50), default="")
    lcls1: Mapped[str] = mapped_column(String(50), default="")
    lcls2: Mapped[str] = mapped_column(String(50), default="")
    lcls3: Mapped[str] = mapped_column(String(50), default="")

    source_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    solo_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    festival_schedules: Mapped[list["FestivalSchedule"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )


class FestivalSchedule(Base):
    __tablename__ = "festival_schedules"
    __table_args__ = (
        UniqueConstraint("location_id", "start_date", "end_date", name="uq_festival_schedule"),
        Index("ix_festival_schedules_period", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100), default="manual")

    location: Mapped[Location] = relationship(back_populates="festival_schedules")


class CourseStop(Base):
    __tablename__ = "course_stops"
    __table_args__ = (
        UniqueConstraint("course_location_id", "stop_order", name="uq_course_stop_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    place_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    stop_order: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (Index("ix_posts_type_created", "type", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(30), default="GENERAL", index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    content: Mapped[str] = mapped_column(Text)
    nickname: Mapped[str] = mapped_column(String(50), default="익명")
    edit_password: Mapped[str] = mapped_column(String(100))
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    comments: Mapped[list["Comment"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    likes: Mapped[list["PostLike"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    nickname: Mapped[str] = mapped_column(String(50), default="익명")
    edit_password: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    post: Mapped[Post] = relationship(back_populates="comments")


class PostLike(Base):
    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("post_id", "client_id", name="uq_post_like_client"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    post: Mapped[Post] = relationship(back_populates="likes")


class TravelRecord(Base):
    __tablename__ = "travel_records"
    __table_args__ = (Index("ix_travel_records_client_visited", "client_id", "visited_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(200))
    memo: Mapped[str] = mapped_column(Text, default="")
    visited_at: Mapped[date] = mapped_column(Date)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["TravelRecordItem"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", order_by="TravelRecordItem.stop_order"
    )


class TravelRecordItem(Base):
    __tablename__ = "travel_record_items"
    __table_args__ = (UniqueConstraint("record_id", "stop_order", name="uq_record_item_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("travel_records.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    stop_order: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")

    record: Mapped[TravelRecord] = relationship(back_populates="items")
