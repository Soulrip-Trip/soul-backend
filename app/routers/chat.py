from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import answer_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    # 외부 AI 호출 대기 중에는 이벤트 루프를 양보하고, DB 검색은 서비스에서 스레드로 넘긴다.
    history = [item.model_dump() for item in payload.history]
    return await answer_chat(db, payload.message, history, payload.language)
