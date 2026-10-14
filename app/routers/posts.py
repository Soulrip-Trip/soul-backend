import json
import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Comment, Post, PostLike
from app.schemas.common import MessageResponse, PaginationMeta
from app.schemas.post import (
    CommentCreate,
    CommentOut,
    CommentUpdate,
    LikeRequest,
    LikeResponse,
    PasswordRequest,
    PostCreate,
    PostListResponse,
    PostOut,
    PostUpdate,
)

router = APIRouter(prefix="/posts", tags=["community"])


def _comment_counts(db: Session, post_ids: list[int]) -> dict[int, int]:
    """목록의 댓글 수를 GROUP BY 한 번으로 계산한다(게시글마다 COUNT 쿼리를 날리는 N+1 방지)."""
    if not post_ids:
        return {}
    rows = db.execute(
        select(Comment.post_id, func.count(Comment.id))
        .where(Comment.post_id.in_(post_ids))
        .group_by(Comment.post_id)
    ).all()
    return {post_id: count for post_id, count in rows}


def _post_out(db: Session, post: Post, comment_count: int | None = None) -> PostOut:
    if comment_count is None:
        comment_count = db.scalar(select(func.count()).select_from(Comment).where(Comment.post_id == post.id)) or 0
    try:
        tags = json.loads(post.tags_json or "[]")
    except json.JSONDecodeError:
        tags = []
    return PostOut(
        id=post.id,
        type=post.type,
        title=post.title,
        content=post.content,
        nickname=post.nickname,
        tags=tags,
        views=post.views,
        likes=post.likes_count,
        comment_count=comment_count,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _verify_password(saved: str, entered: str) -> None:
    if saved != entered:
        raise HTTPException(status_code=403, detail="비밀번호가 일치하지 않습니다.")


@router.get("", response_model=PostListResponse)
def list_posts(
    q: str | None = None,
    type: str | None = None,
    sort: Literal["latest", "views", "likes"] = "latest",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PostListResponse:
    filters = []
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(Post.title.ilike(like), Post.content.ilike(like), Post.tags_json.ilike(like)))
    if type:
        filters.append(Post.type == type)

    total = db.scalar(select(func.count()).select_from(Post).where(*filters)) or 0
    stmt = select(Post).where(*filters)
    if sort == "views":
        stmt = stmt.order_by(Post.views.desc(), Post.created_at.desc())
    elif sort == "likes":
        stmt = stmt.order_by(Post.likes_count.desc(), Post.created_at.desc())
    else:
        stmt = stmt.order_by(Post.created_at.desc())

    items = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
    comment_counts = _comment_counts(db, [item.id for item in items])
    return PostListResponse(
        items=[_post_out(db, item, comment_counts.get(item.id, 0)) for item in items],
        meta=PaginationMeta(total=total, page=page, size=limit, pages=max(1, math.ceil(total / limit))),
    )


@router.post("", response_model=PostOut, status_code=201)
def create_post(payload: PostCreate, db: Session = Depends(get_db)) -> PostOut:
    post = Post(
        type=payload.type.upper(),
        title=payload.title.strip(),
        content=payload.content.strip(),
        nickname=payload.nickname.strip() or "익명",
        edit_password=payload.password,
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _post_out(db, post)


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)) -> PostOut:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    post.views += 1
    db.commit()
    db.refresh(post)
    return _post_out(db, post)


@router.patch("/{post_id}", response_model=PostOut)
def update_post(post_id: int, payload: PostUpdate, db: Session = Depends(get_db)) -> PostOut:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    _verify_password(post.edit_password, payload.password)

    if payload.type is not None:
        post.type = payload.type.upper()
    if payload.title is not None:
        post.title = payload.title.strip()
    if payload.content is not None:
        post.content = payload.content.strip()
    if payload.nickname is not None:
        post.nickname = payload.nickname.strip() or "익명"
    if payload.tags is not None:
        post.tags_json = json.dumps(payload.tags, ensure_ascii=False)

    db.commit()
    db.refresh(post)
    return _post_out(db, post)


@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    password: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> Response:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    _verify_password(post.edit_password, password)
    db.delete(post)
    db.commit()
    return Response(status_code=204)


@router.post("/{post_id}/verify-password", response_model=MessageResponse)
def verify_post_password(
    post_id: int,
    payload: PasswordRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    _verify_password(post.edit_password, payload.password)
    return MessageResponse(message="비밀번호가 확인되었습니다.")


@router.post("/{post_id}/likes", response_model=LikeResponse)
def toggle_like(post_id: int, payload: LikeRequest, db: Session = Depends(get_db)) -> LikeResponse:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    like = db.scalar(
        select(PostLike).where(PostLike.post_id == post_id, PostLike.client_id == payload.client_id)
    )
    if like:
        db.delete(like)
        post.likes_count = max(0, post.likes_count - 1)
        liked = False
    else:
        db.add(PostLike(post_id=post_id, client_id=payload.client_id))
        post.likes_count += 1
        liked = True
    db.commit()
    return LikeResponse(liked=liked, likes_count=post.likes_count)


@router.get("/{post_id}/comments", response_model=list[CommentOut])
def list_comments(post_id: int, db: Session = Depends(get_db)) -> list[CommentOut]:
    if db.get(Post, post_id) is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    comments = db.scalars(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at.asc())
    ).all()
    return [CommentOut.model_validate(item) for item in comments]

@router.get("/{post_id}/likes/status")
def get_like_status(
    post_id: int,
    clientId: str,
    db: Session = Depends(get_db),
):
    like = (
        db.query(PostLike)
        .filter(
            PostLike.post_id == post_id,
            PostLike.client_id == clientId,
        )
        .first()
    )

    return {
        "liked": like is not None,
    }

@router.post("/{post_id}/comments", response_model=CommentOut, status_code=201)
def create_comment(
    post_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
) -> CommentOut:
    if db.get(Post, post_id) is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    comment = Comment(
        post_id=post_id,
        content=payload.content.strip(),
        nickname=payload.nickname.strip() or "익명",
        edit_password=payload.password,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentOut.model_validate(comment)


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    db: Session = Depends(get_db),
) -> CommentOut:
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    _verify_password(comment.edit_password, payload.password)
    comment.content = payload.content.strip()
    if payload.nickname is not None:
        comment.nickname = payload.nickname.strip() or "익명"
    db.commit()
    db.refresh(comment)
    return CommentOut.model_validate(comment)


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: int,
    password: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> Response:
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    _verify_password(comment.edit_password, password)
    db.delete(comment)
    db.commit()
    return Response(status_code=204)
