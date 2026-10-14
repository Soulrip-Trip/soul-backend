import logging

import openai
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.ai_insight import TodayInsightResponse
from app.services.ai_insight_service import (
    AIInsightConfigError,
    AIInsightDataError,
    AIInsightResponseError,
    ai_insight_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai-insights",
    tags=["AI Insights"],
)


@router.post(
    "/today",
    response_model=TodayInsightResponse,
    status_code=status.HTTP_200_OK,
)
async def create_today_insight(
    db: Session = Depends(get_db),
) -> TodayInsightResponse:
    try:
        return await ai_insight_service.create_today_insight(db)

    except AIInsightConfigError as error:
        # 서버 설정 문제는 원인을 숨기지 않고 그대로 알린다.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    except AIInsightDataError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    except AIInsightResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI 응답이 올바르지 않습니다: {error}",
        ) from error

    except (openai.APIConnectionError, openai.APITimeoutError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI 서버에 연결할 수 없습니다.",
        ) from error

    except openai.RateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenAI API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
        ) from error

    except openai.APIStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI API 요청 중 오류가 발생했습니다. status={error.status_code}",
        ) from error

    except Exception as error:
        logger.exception("AI insight error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 인사이트 생성 중 오류가 발생했습니다.",
        ) from error
