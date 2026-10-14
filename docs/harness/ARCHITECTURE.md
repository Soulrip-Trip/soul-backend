# Backend Architecture

Soulrip Backend는 FastAPI를 중심으로 HTTP, Schema, 도메인 로직, DB를 분리한다.

## Request Flow

```text
Vue Frontend
   ↓ HTTP
FastAPI Router
   ↓
Pydantic Schema
   ↓
Service / Query Logic
   ↓
SQLAlchemy ORM
   ↓
SQLite
```

## Layers

### Application

`app/main.py`가 앱 인스턴스, lifespan(DB·인덱스 보장, 공유 HTTP 클라이언트, RAG 인덱스 로드), 미들웨어(ProcessTime → CORS → GZip), Router 등록을 담당한다.

### Core

- `config.py`: DB URL, API prefix, CORS, AI provider key/model, RAG 모드, 캐시 TTL, admin key
- `cache.py`: 프로세스 메모리 LRU+TTL 캐시(chat, meta, ai-insight, rag)
- `http_client.py`: 외부 호출용 공유 `httpx.AsyncClient`
- `middleware.py`: `X-Process-Time` 순수 ASGI 미들웨어

### Sync / Async 원칙

DB 중심 endpoint는 `def`(스레드풀 실행)로 둔다. 외부 AI를 기다리는 `/chat`, `/ai-insights`만 `async def`이고, 내부의 동기 DB 작업은 `anyio.to_thread`로 넘긴다.

### RAG

`rag-server/`가 원천 자료(`data/`), 빌드 결과(`index/`), 검색 패키지(`rag/`)를 가진다. 백엔드는 `RAG_MODE=embedded`일 때 인덱스를 프로세스에 직접 로드하고, `remote`일 때 rag-server API를 호출한다. 어떤 경우든 RAG 실패는 챗봇 실패가 아니다.

### Router

도메인별 endpoint를 제공한다.

```text
places
festivals
courses
posts
travel_records
chat
insights
ai_insights
meta
health
```

### Schema

Pydantic 모델이 request/response 계약을 정의한다. Frontend는 이 계약의 소비자이므로 Schema 변경은 full-stack 변경으로 취급한다.

### Database

SQLAlchemy ORM을 사용하며 `Location`이 관광 데이터의 중심 모델이다. FestivalSchedule, CourseStop, Post, Comment, PostLike, TravelRecord 등이 기능별 상태를 저장한다.

### Service

외부 AI 호출, 추천 알고리즘, serializer, importer처럼 Router에서 재사용하거나 분리할 가치가 있는 로직을 담당한다.

## Architectural Principle

모든 기능을 무조건 Service 계층으로 이동시키는 것이 목표가 아니다. 현재 규모에서는 간단한 query가 Router에 존재할 수 있으며, 하네스의 목적은 계층 수를 늘리는 것이 아니라 **책임의 위치를 예측 가능하게 유지하는 것**이다.
