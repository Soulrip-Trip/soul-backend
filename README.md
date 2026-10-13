# Soulrip — Backend

> **Discover Solo → Plan Solo → Share Solo**  
> 혼자 떠나는 서울에서 나에게 맞는 장소와 여행 경험을 발견하고 공유하는 **AI 기반 Solo Travel Hub**이다.

Soulrip은 서울 지역 공공 관광 데이터를 혼행 사용자의 관점에서 재구성한 풀스택 웹 서비스이다. 사용자는 프론트엔드에서 장소와 축제를 탐색하고, AI에게 여행 정보를 질문하며, 익명 커뮤니티와 여행 기록을 통해 자신의 경험을 남길 수 있다.

이 저장소는 Soulrip 전체 서비스 중 **Backend API와 데이터 계층**을 담당한다. Vue 기반 프론트엔드와 REST API로 연결되며, 서울 관광 JSON 데이터를 SQLite에 적재하고 장소·축제·코스·커뮤니티·여행 기록·AI 기능에 필요한 API를 제공한다.

## Project Repositories

| Repository | Role | Link |
| --- | --- | --- |
| Frontend | Vue 3 기반 사용자 화면과 상호작용 | https://github.com/Soulrip-Trip/soul-frontend |
| Backend | FastAPI 기반 REST API, 데이터 처리, AI 연동 | https://github.com/Soulrip-Trip/soul-backend |

두 저장소는 하나의 Soulrip 서비스를 구성한다. 프론트엔드는 사용자 경험과 화면 상태를 담당하고, 백엔드는 데이터 조회·가공·영속화와 외부 AI API 연동을 담당한다.

---

## Project Overview

| Item | Description |
| --- | --- |
| Service | Soulrip |
| Region | Seoul |
| Development Period | n일 |
| Team | 3명 |
| Frontend | Vue 3, TypeScript, Vite |
| Backend | FastAPI, Python |
| ORM | SQLAlchemy |
| Database | SQLite |
| AI | Gemini 기반 지역 정보 챗봇, OpenAI 기반 AI Insight |
| Deployment | Render |
| Data | 서울 지역 공공 관광 JSON 데이터 |

---

## Service Concept

Soulrip의 핵심 사용자 흐름은 다음과 같다.

```text
Discover Solo
      ↓
Plan Solo
      ↓
Share Solo
```

### Discover Solo

서울의 관광지, 문화시설, 레포츠, 쇼핑, 숙박, 여행코스, 축제·공연·행사 데이터를 탐색하는 단계이다. 백엔드는 검색, 카테고리, 자치구, 지도 좌표, 주변 장소, 상세 정보 등에 필요한 REST API를 제공한다.

### Plan Solo

사용자의 현재 상황과 관심사에 맞는 여행 선택지를 구체화하는 단계이다. 여행코스 추천 API와 지역 정보 챗봇, AI Insight를 통해 저장된 서울 데이터를 여행 의사결정에 활용한다.

### Share Solo

실제 혼행 경험을 기록하고 다른 사용자와 공유하는 단계이다. 익명 커뮤니티 CRUD, 댓글, 좋아요, 브라우저 `clientId` 기반 여행 기록 API를 제공한다.

---

## Full-stack Architecture

```text
┌─────────────────────────────────────────────┐
│               Soulrip Frontend              │
│          Vue 3 + TypeScript + Vite          │
│                                             │
│  Place / Festival / Course / Community      │
│  Travel Record / Chat UI / AI Insight UI    │
└──────────────────────┬──────────────────────┘
                       │ REST API
                       │ /api/v1
                       ▼
┌─────────────────────────────────────────────┐
│               Soulrip Backend               │
│                 FastAPI                     │
│                                             │
│  Router → Schema → Service → DB             │
│                                             │
│  Places / Festivals / Courses / Posts       │
│  Travel Records / Chat / AI Insights        │
└───────────────┬─────────────────┬───────────┘
                │                 │
                ▼                 ▼
       ┌────────────────┐  ┌──────────────────┐
       │ SQLite         │  │ External AI APIs │
       │ SQLAlchemy     │  │ Gemini / OpenAI  │
       └───────┬────────┘  └──────────────────┘
               │
               ▼
       ┌────────────────┐
       │ Seoul JSON Data│
       │ + Schedules    │
       └────────────────┘
```

프론트엔드가 API 계약을 소비하고 백엔드가 데이터와 도메인 규칙의 기준을 제공하는 구조이다. API 필드명이나 동작을 변경할 때는 한 저장소만 보고 판단하지 않고 프론트엔드 영향 범위도 함께 확인해야 한다.

---

## Backend Architecture

```text
app/
├─ core/                 # 환경설정과 공통 설정
├─ db/                   # DB 연결과 SQLAlchemy 모델
├─ routers/              # HTTP endpoint와 요청 흐름
├─ schemas/              # Pydantic 요청/응답 계약
├─ services/             # AI, 추천, 직렬화, 데이터 적재 로직
└─ main.py               # FastAPI 앱과 Router 등록

data/
├─ festival_schedules.json
└─ festival_schedules.example.json

scripts/
├─ check_data.py
└─ seed_data.py
```

새 기능은 기존 구조에서 가장 가까운 도메인의 Router, Schema, Service, Model 패턴을 먼저 확인한 뒤 확장한다.

---

## Core Features

### Place Discovery

- 장소 목록 및 상세 조회를 제공한다.
- 검색어, 카테고리, 자치구 등의 조건을 처리한다.
- 지도 표시용 장소 데이터와 주변 장소 검색을 지원한다.
- 좌표 기반 계산은 기존 추천 유틸리티를 재사용한다.

### Festival Discovery

- 축제 목록과 상세 정보를 제공한다.
- 월별 캘린더와 특정 날짜 기준 조회를 지원한다.
- 실제 행사 일정은 `FestivalSchedule`을 기준으로 관리한다.
- 관리자 키를 사용하는 일정 보완 API가 존재한다.

### Course Recommendation

- 저장된 여행코스 목록과 상세를 제공한다.
- 후보 장소를 필터링한 뒤 거리 기반 순서를 계산하여 간단한 혼행 코스를 생성한다.
- 추천 결과는 사용자의 자치구, 콘텐츠 유형, 이동수단, 소요시간 등의 입력을 고려한다.

### Anonymous Community

- 로그인 없는 익명 게시글 CRUD를 제공한다.
- 댓글 작성·수정·삭제를 제공한다.
- 좋아요 기능을 제공한다.
- 수정과 삭제 권한은 현재 비밀번호 기반 흐름을 사용한다.

### Travel Records

- 브라우저의 `clientId`를 기준으로 사용자의 여행 기록을 구분한다.
- 목록, 상세, 생성, 수정, 삭제 API를 제공한다.
- 별도의 회원 시스템이 없다는 서비스 전제를 유지한다.

### AI Local Guide

지역 정보 챗봇은 다음 흐름으로 동작한다.

```text
사용자 질문
   ↓
검색어 정규화
   ↓
SQLite에서 장소 / 축제 / 게시글 검색
   ↓
검색된 데이터로 Context 생성
   ↓
Gemini에 Context + History 전달
   ↓
답변 + Source 반환
```

AI가 임의의 서울 정보를 생성하도록 하지 않고 **저장된 데이터 검색 결과를 우선 근거로 사용**하는 구조이다. Gemini API 키가 없거나 외부 호출이 실패해도 검색 결과를 기반으로 fallback 응답을 반환한다.

### AI Insight

AI Insight는 저장된 장소와 축제 데이터를 추려 OpenAI에 전달하고 구조화된 JSON 응답을 생성하는 기능이다.

- 입력 데이터에 없는 장소를 추측하지 않는다.
- 이미지 URL은 입력 데이터에 존재하는 URL만 사용한다.
- 구조화된 JSON Schema를 기준으로 응답을 검증한다.
- 관광 데이터가 없는 경우 임의의 결과를 생성하지 않는다.

---

## Data Sources

현재 importer가 인식하는 콘텐츠 유형은 다음과 같다.

| contentTypeId | Category |
| ---: | --- |
| 12 | 관광지 |
| 14 | 문화시설 |
| 15 | 축제공연행사 |
| 25 | 여행코스 |
| 28 | 레포츠 |
| 32 | 숙박 |
| 38 | 쇼핑 |
| 39 | 음식점 |

원본 JSON 파일은 `scripts.seed_data`와 `app/services/importer.py`를 통해 SQLite에 적재한다.

### Festival Schedule Constraint

원본 축제 JSON의 `createdtime`, `modifiedtime`은 데이터 생성·수정 시각이며 실제 행사 시작일과 종료일이 아니다.

따라서 축제 일정 기능에서는 해당 값을 행사 일정으로 사용하지 않는다. 실제 일정은 `data/festival_schedules.json`의 `startDate`, `endDate`를 `FestivalSchedule`에 적재하여 사용한다.

### Restaurant Data Constraint

importer는 `서울_음식점.json`을 인식할 수 있지만 실제 데이터 파일이 존재하지 않으면 음식점 데이터를 임의로 생성하지 않는다.

---

## API Overview

기본 API prefix는 다음과 같다.

```text
/api/v1
```

### Places

```http
GET /api/v1/places
GET /api/v1/places/map
GET /api/v1/places/nearby
GET /api/v1/places/{contentId}
```

### Festivals

```http
GET  /api/v1/festivals
GET  /api/v1/festivals/calendar?year=2026&month=7
GET  /api/v1/festivals/on-date?date=YYYY-MM-DD
GET  /api/v1/festivals/{contentId}
POST /api/v1/festivals/{contentId}/schedules
```

일정 생성 API는 `X-Admin-Key` 검증을 사용한다.

### Courses

```http
GET  /api/v1/courses
GET  /api/v1/courses/{contentId}
POST /api/v1/courses/recommend
```

### Community

```http
GET    /api/v1/posts
POST   /api/v1/posts
GET    /api/v1/posts/{id}
PATCH  /api/v1/posts/{id}
DELETE /api/v1/posts/{id}?password=...

POST   /api/v1/posts/{id}/verify-password
POST   /api/v1/posts/{id}/likes
GET    /api/v1/posts/{id}/comments
POST   /api/v1/posts/{id}/comments
PATCH  /api/v1/posts/comments/{commentId}
DELETE /api/v1/posts/comments/{commentId}?password=...
```

### Travel Records

```http
GET    /api/v1/travel-records?clientId=...
POST   /api/v1/travel-records
GET    /api/v1/travel-records/{id}?clientId=...
PATCH  /api/v1/travel-records/{id}
DELETE /api/v1/travel-records/{id}?clientId=...
```

### Chat & Insights

```http
POST /api/v1/chat
GET  /api/v1/insights/today
POST /api/v1/ai-insights/today
```

### Meta & Health

```http
GET /api/v1/meta/categories
GET /api/v1/meta/districts
GET /api/v1/meta/stats
GET /api/v1/health
```

전체 요청/응답 스키마는 실행 후 Swagger에서 확인할 수 있다.

---

## Frontend Integration

Frontend repository:

```text
https://github.com/skyblue1232/soulrip-frontend
```

프론트엔드의 API base URL은 다음과 같이 백엔드 `/api/v1` 경로를 바라보도록 설정한다.

```env
VITE_API_BASE_URL=https://soulrip-backend.onrender.com/api/v1
```

대표적인 연결 관계는 다음과 같다.

```text
Frontend Place API       → Backend /places
Frontend Festival API    → Backend /festivals
Frontend Community API   → Backend /posts
Frontend ChatBot         → Backend /chat
Frontend Course Feature  → Backend /courses
Frontend Travel Record   → Backend /travel-records
```

API 응답 필드를 변경하면 프론트엔드의 `src/services/api.ts`, `src/types`, 관련 View/Component까지 영향 범위를 확인해야 한다.

---

## Environment Variables

`.env.example`을 기준으로 환경변수를 설정한다.

```env
DATABASE_URL=sqlite:///./soulrip.db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
ADMIN_KEY=change-me
```

AI Insight를 사용할 경우 현재 `app/core/config.py`에서 사용하는 OpenAI 설정도 `.env`에 추가한다.

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

비밀키는 저장소에 커밋하지 않는다.

---

## Getting Started

### 1. Virtual Environment

```bash
python -m venv .venv
```

Windows Git Bash 기준 활성화 방법은 다음과 같다.

```bash
source .venv/Scripts/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment

```bash
cp .env.example .env
```

### 4. Seed Data

필요한 서울 JSON 데이터가 준비된 상태에서 실행한다.

```bash
python -m scripts.seed_data
```

### 5. Run Server

```bash
uvicorn app.main:app --reload
```

### 6. API Documentation

```text
Local API     http://127.0.0.1:8000/api/v1
Swagger       http://127.0.0.1:8000/docs
Production    https://soulrip-backend.onrender.com/api/v1
```

---

## Security Notes

현재 프로젝트의 익명 커뮤니티는 프로젝트 요구사항에 맞춰 게시글과 댓글 수정용 비밀번호를 단순 비교하는 구조가 포함되어 있다.

실제 운영 환경으로 확장할 경우 다음 사항을 우선 개선해야 한다.

- 비밀번호 해시 저장
- 관리자 키 관리 강화
- 요청 rate limit
- 입력값 검증 강화
- 운영 DB 분리
- secret manager 적용
- 로그에서 민감정보 제거

하네스 문서는 현재 구현을 무조건 정답으로 고정하는 것이 아니라 **현재 동작을 보존하면서 운영 수준으로 개선할 때 변경 영향 범위를 명확하게 만들기 위한 기준**이다.

---

## Harness Engineering

이 저장소에는 AI 코딩 도구가 Soulrip Backend의 구조와 도메인 규칙을 반복해서 추론하지 않아도 되도록 하네스 문서를 함께 관리한다.

```text
AGENTS.md
.github/copilot-instructions.md
.github/instructions/*.instructions.md
.github/prompts/*.prompt.md
docs/harness/
```

하네스는 다음 네 계층으로 구성한다.

```text
Global     → 프로젝트 전체 불변조건
Domain     → 기능별 비즈니스 규칙
Local      → 경로별 코드 작성 규칙
Workflow   → 반복 작업 실행 절차
```

자세한 사용법은 [`docs/harness/README.md`](docs/harness/README.md)를 참고한다.

---

## Verification

현재 저장소에는 별도의 정적 분석 또는 테스트 명령이 명시되어 있지 않으므로 존재하지 않는 `pytest`, `ruff`, `mypy` 명령을 하네스가 임의로 가정하지 않는다.

기본 문법 검증은 다음과 같이 수행할 수 있다.

```bash
python -m compileall app scripts
```

데이터를 사용하는 기능을 변경한 경우 개발 DB에서 시드와 API 동작을 추가로 검증한다.

```bash
python -m scripts.seed_data
uvicorn app.main:app --reload
```

그 뒤 `/docs`에서 변경된 API 계약과 상태코드를 확인한다.

---

## Development Principles

Soulrip Backend는 많은 추상화를 만드는 것보다 **현재 도메인 규칙을 명확하게 유지하는 것**을 우선한다.

```text
요구사항 확인
   ↓
관련 Router / Schema / Service / Model 탐색
   ↓
Frontend API 계약 영향 확인
   ↓
최소 변경 구현
   ↓
데이터 불변조건 검증
   ↓
API / 오류 / fallback 확인
   ↓
문서와 Harness 동기화
```

특히 AI가 코드를 생성한 경우에도 SQL 조건, 응답 Schema, 상태코드, 데이터 출처, 프론트엔드 계약을 개발자가 직접 검토하는 것을 기본 원칙으로 한다.
