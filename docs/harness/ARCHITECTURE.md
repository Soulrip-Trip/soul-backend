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

`app/main.py`가 앱 인스턴스, CORS, Router 등록을 담당한다.

### Core

`app/core/config.py`가 DB URL, API prefix, CORS, AI provider key/model, admin key를 관리한다.

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
