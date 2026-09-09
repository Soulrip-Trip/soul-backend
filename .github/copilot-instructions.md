# Soulrip Backend Copilot Instructions

Soulrip Backend에서 코드를 생성하거나 수정할 때 다음 규칙을 기본 컨텍스트로 사용한다.

## Project Context

이 저장소는 Vue 기반 Soulrip 프론트엔드가 사용하는 FastAPI REST API 서버이다. 주요 도메인은 장소, 축제, 여행코스, 익명 커뮤니티, 여행 기록, 지역 정보 챗봇, AI Insight이다.

## Architecture

```text
HTTP Request
   ↓
Router
   ↓
Pydantic Schema
   ↓
Service / Domain Logic
   ↓
SQLAlchemy Model
   ↓
SQLite
```

모든 기능이 반드시 Service를 거쳐야 한다는 의미는 아니다. 기존 Router에 단순 query가 구현되어 있다면 해당 패턴을 우선 존중하고, 중복되거나 외부 연동이 필요한 로직만 Service 분리를 고려한다.

## Coding Rules

- 현재 코드 스타일과 타입 힌트를 우선한다.
- FastAPI `Depends(get_db)` Session 패턴을 유지한다.
- API 응답은 Pydantic response model을 우선 사용한다.
- 사용자 입력은 Query/Schema 제약으로 가능한 범위에서 조기에 검증한다.
- SQLAlchemy query의 필터, 정렬, limit, offset 의미를 명확하게 유지한다.
- 새 환경변수는 `app/core/config.py`의 `Settings`와 `.env.example`을 함께 갱신한다.
- 새 Router를 추가하면 `app/main.py`에 등록한다.

## Domain Constraints

- 축제 일정에 원본 JSON의 생성/수정 시각을 사용하지 않는다.
- 챗봇은 검색된 데이터 문맥 밖의 정보를 추측하지 않는다.
- Gemini 실패 시 챗봇 fallback을 제거하지 않는다.
- AI Insight는 OpenAI 구조화 응답과 이미지 URL 검증을 유지한다.
- 익명 커뮤니티의 비밀번호와 `clientId` 기반 흐름을 임의로 로그인 방식으로 바꾸지 않는다.
- 좌표가 없는 장소는 거리 기반 계산에서 안전하게 처리한다.

## Full-stack Contract

Backend API를 변경할 때 다음 Frontend 위치에 미치는 영향을 고려한다.

```text
soulrip-frontend/src/services/api.ts
soulrip-frontend/src/types/
soulrip-frontend/src/views/
soulrip-frontend/src/components/
```

프론트 코드가 현재 작업공간에 없더라도 이미 소비되고 있는 API라는 전제로 호환성을 우선한다.

## Verification

저장소에 없는 테스트 도구를 임의로 가정하지 않는다. 최소한 다음 문법 검증을 수행한다.

```bash
python -m compileall app scripts
```

API 계약이 바뀐 경우 로컬 서버와 `/docs`에서 실제 Schema를 확인한다.
