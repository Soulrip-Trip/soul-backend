from contextlib import asynccontextmanager

from anyio import to_thread
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core import http_client
from app.core.config import get_settings
from app.core.middleware import ProcessTimeMiddleware
from app.db.database import init_db
from app.routers import (
    ai_insights,
    chat,
    courses,
    festivals,
    health,
    insights,
    meta,
    places,
    posts,
    travel_records,
)
from app.services.rag_service import rag_service

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 기동 시 한 번만: 테이블·인덱스 보장, 외부 HTTP 연결 풀 생성, RAG 인덱스 메모리 로드
    await to_thread.run_sync(init_db)
    await http_client.startup()
    await to_thread.run_sync(rag_service.startup)
    yield
    await http_client.shutdown()


app = FastAPI(
    title=settings.app_name,
    version="1.1.0",
    description="서울 혼행 정보, 축제, 코스, 여행 기록, 익명 커뮤니티, RAG 챗봇 API",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)
app.add_middleware(ProcessTimeMiddleware)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(meta.router, prefix=settings.api_prefix)
app.include_router(places.router, prefix=settings.api_prefix)
app.include_router(festivals.router, prefix=settings.api_prefix)
app.include_router(courses.router, prefix=settings.api_prefix)
app.include_router(posts.router, prefix=settings.api_prefix)
app.include_router(travel_records.router, prefix=settings.api_prefix)
app.include_router(insights.router, prefix=settings.api_prefix)
app.include_router(ai_insights.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
