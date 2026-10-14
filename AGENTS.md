# Soulrip Backend Agent Guide

이 문서는 Soulrip 백엔드 저장소에서 AI 코딩 에이전트가 작업할 때 따라야 하는 최상위 가이드이다.

## 1. Project Purpose

Soulrip은 서울 공공 관광 데이터를 혼행 사용자의 관점에서 탐색하고, 여행 선택지를 구체화하고, 경험을 공유하도록 지원하는 풀스택 서비스이다.

이 저장소는 Backend를 담당하며 다음 책임을 가진다.

- 서울 관광 JSON 데이터를 SQLite에 적재한다.
- Vue 프론트엔드가 사용하는 REST API를 제공한다.
- 장소, 축제, 코스, 커뮤니티, 여행 기록 도메인을 관리한다.
- Gemini 기반 지역 정보 챗봇을 제공한다.
- OpenAI 기반 AI Insight를 제공한다.

## 2. Tech Stack

- Python을 사용한다.
- FastAPI를 HTTP 계층으로 사용한다.
- Pydantic Schema를 요청/응답 계약으로 사용한다.
- SQLAlchemy ORM을 사용한다.
- SQLite를 기본 DB로 사용한다.
- `httpx`를 외부 HTTP 호출에 사용한다.
- Gemini API와 OpenAI API를 AI 기능에 사용한다.
- RAG는 자체 BM25 인덱스(`rag-server`)와 `numpy`를 사용한다. 인덱스 빌드에만 `pypdf`, `openpyxl`을 사용한다.

새 라이브러리는 현재 스택으로 해결하기 어려운 명확한 이유가 있을 때만 추가한다.

## 3. Repository Structure First

```text
app/
├─ core/        # 환경설정, 캐시, 공유 HTTP 클라이언트, 미들웨어
├─ db/          # DB 연결과 모델
├─ routers/     # FastAPI endpoint
├─ schemas/     # Pydantic request/response
├─ services/    # 도메인 서비스와 외부 API(chat, rag, gemini, ai_insight …)
└─ main.py      # 앱 구성(lifespan, 미들웨어)과 router 등록

rag-server/     # RAG 원천 자료(data/), 인덱스(index/), 검색 패키지(rag/), 빌드 스크립트, remote 모드 API
data/           # 보완 데이터
scripts/        # 시드 및 데이터 점검
docs/           # 하네스, 프론트엔드 연동 가이드
```

새 기능을 구현할 때 기존 도메인에서 가장 가까운 Router → Schema → Service → Model 흐름을 먼저 찾는다. 기존 구조를 무시한 Repository 계층, Manager 계층, 범용 Base 클래스 등을 먼저 만들지 않는다.

## 4. Layer Responsibilities

- `main.py`는 FastAPI 앱 구성(lifespan, 미들웨어, CORS), Router 등록만 담당한다.
- `core`는 환경변수, 공통 설정, 프로세스 캐시, 공유 HTTP 클라이언트를 담당한다.
- DB 중심 endpoint는 `def`로 둔다. 외부 AI를 기다리는 endpoint만 `async def`로 두고, 그 안의 동기 DB 작업은 `anyio.to_thread`로 넘긴다.
- `routers`는 HTTP 입력, dependency, 상태코드, 예외 매핑을 담당한다.
- `schemas`는 외부 요청/응답 계약을 담당한다.
- `services`는 검색, 추천, 외부 AI 호출, 직렬화, 데이터 적재 등 재사용 로직을 담당한다.
- `db/models.py`는 영속 모델과 관계를 담당한다.
- `scripts`는 개발/초기화 작업을 수행하며 런타임 API 로직과 섞지 않는다.

## 5. API Contract Rules

- 기본 API prefix는 `/api/v1`을 유지한다.
- 이미 프론트엔드가 사용하는 필드명은 이유 없이 변경하지 않는다.
- 요청/응답 구조를 변경하면 `schemas`와 프론트엔드 영향 범위를 함께 확인한다.
- Router에서 dict를 임의로 조립하기보다 기존 Pydantic response model을 우선 사용한다.
- 목록 API의 pagination 의미를 도메인별로 일관되게 유지한다.
- 존재하지 않는 리소스는 기존 endpoint의 404 패턴을 따른다.
- 사용자 입력 오류와 서버 오류를 같은 상태코드로 처리하지 않는다.

## 6. Database Rules

- Session은 `Depends(get_db)` 흐름을 우선한다.
- 조회 시 필요한 조건과 정렬 기준을 명시한다.
- 새 모델 필드를 추가하면 기존 SQLite DB와 시드 데이터에 미치는 영향을 확인한다.
- `content_id` 등 외부 데이터 식별자의 의미를 임의로 바꾸지 않는다.
- 관계형 데이터 삭제 시 댓글, 좋아요, 일정 등 관련 데이터 영향을 확인한다.
- 대량 데이터 루프에서 불필요한 반복 query가 생기지 않는지 확인한다.

## 7. Soulrip Domain Invariants

### Places

- 장소의 중심 엔티티는 `Location`이다.
- `content_type_id`와 `content_type`의 기존 의미를 유지한다.
- 위도와 경도, 이미지, 설명은 비어 있을 수 있다.
- 거리 계산은 기존 `haversine_km` 등 추천 유틸리티를 우선 재사용한다.

### Festivals

- 원본 JSON의 `createdtime`, `modifiedtime`은 행사 일정이 아니다.
- 실제 일정은 `FestivalSchedule.start_date`, `FestivalSchedule.end_date`를 기준으로 한다.
- `festival_schedules.json`을 통한 보완 흐름을 유지한다.
- 관리자 일정 생성 API를 변경할 때 `X-Admin-Key` 검증을 확인한다.

### Courses

- 저장된 여행코스와 동적으로 생성하는 추천 코스를 구분한다.
- 추천은 기존 후보 필터와 거리 기반 정렬 방식을 먼저 유지한다.
- 지도 좌표가 없는 장소를 거리 기반 추천에 조용히 포함하지 않는다.

### Community

- 회원가입 없는 익명 커뮤니티라는 전제를 유지한다.
- 게시글과 댓글 수정/삭제의 비밀번호 흐름을 깨뜨리지 않는다.
- 좋아요 데이터와 `likes_count`가 불일치하지 않도록 변경 범위를 확인한다.
- `tags_json` 파싱 실패 시 기존 fallback 동작을 고려한다.

### Travel Records

- 사용자 식별은 현재 브라우저 `clientId` 기반이다.
- 다른 `clientId`의 기록이 노출되거나 수정되지 않도록 소유권 조건을 확인한다.

### Chatbot

- 챗봇은 저장된 서울 데이터와 커뮤니티 검색 결과를 근거로 답한다.
- 데이터에 없는 영업시간, 가격, 축제 날짜 등을 추측하지 않는다.
- 최근 history는 현재 최대 10개 메시지를 AI 호출에 활용한다.
- Gemini 키가 없거나 호출이 실패하면 fallback 응답을 유지한다.
- 응답의 `sources`, `suggestions`, `used_ai` 계약을 보존한다.
- 지원 언어는 `ko`, `en`, `ja`, `zh`, `fr`, `es`, `de` 흐름을 유지한다.
- RAG는 서버 내부에서만 동작한다. 요청마다 원천 자료를 다시 읽거나 전체 자료를 프롬프트에 넣지 않고, 미리 빌드한 인덱스의 top-k 근거만 전달한다.
- 실태조사 근거에는 연도·조사 대상·확정/잠정 라벨을 유지한다. 2026 외국인 자료는 잠정치로 답변해야 한다.
- RAG가 실패하거나 인덱스가 없어도 DB 검색만으로 응답한다.

### RAG Data

- 원천 자료의 메타데이터와 색인 여부는 `rag-server/data/manifest.json`이 기준이다.
- 응답자 원자료(`rag-server/data/raw`), 설문지, 코드북은 색인하지 않는다.
- 원천 자료나 loader를 바꾸면 `rag-server`에서 `python -m scripts.build_index`로 인덱스를 다시 빌드하고 `index/`를 함께 커밋한다.
- 출처 URL·제공 기관을 확인하지 못한 경우 추측해서 채우지 않고 빈 값으로 둔다.

### AI Insight

- AI Insight는 OpenAI를 사용한다.
- 입력된 장소와 축제 데이터만 근거로 생성한다.
- JSON Schema 구조를 유지한다.
- 입력에 없는 이미지 URL을 생성하거나 수정하지 않는다.
- `OPENAI_API_KEY`가 없을 때 오류 원인을 숨기지 않는다.

## 8. Data Import Rules

- importer가 인식하는 원본 파일명과 `contentTypeId` 매핑을 임의로 변경하지 않는다.
- 빈 문자열, 숫자, 좌표, 날짜 변환에서 기존 정규화 함수를 우선 재사용한다.
- import는 동일 `content_id`가 존재할 때 update하는 현재 의미를 유지한다.
- `festival_schedules.json`의 날짜는 `%Y-%m-%d` 형식을 사용한다.
- 데이터 파일이 없다고 임의의 sample 데이터를 운영 DB에 생성하지 않는다.

## 9. Secrets and Configuration

- API key, admin key, DB URL을 코드에 하드코딩하지 않는다.
- 환경변수는 `Settings`를 통해 읽는다(rag-server는 `RagSettings`).
- `RAG_API_KEY` 등 내부 호출 키도 코드와 프론트엔드에 두지 않는다.
- `.env`는 커밋하지 않는다.
- `.env.example`에는 실제 비밀값을 넣지 않는다.
- CORS origin을 변경하면 프론트엔드 배포 origin과 함께 검토한다.

## 10. Change Workflow

1. 요청을 사용자 기능과 API 계약 단위로 다시 정의한다.
2. 관련 Router → Schema → Service → Model → Script/Data 순으로 영향 범위를 찾는다.
3. 프론트엔드가 사용하는 endpoint와 응답 필드를 확인한다.
4. 기존 도메인 불변조건을 확인한다.
5. 최소 변경으로 구현한다.
6. 정상, 빈 결과, 잘못된 입력, 외부 API 실패를 검증한다.
7. Python 문법 검증과 Swagger 계약을 확인한다.
8. 구조나 계약이 바뀌면 README와 하네스 문서도 함께 갱신한다.

## 11. Verification Commands

현재 저장소에는 별도 테스트/린트 도구가 명시되어 있지 않다. 존재하지 않는 검증 명령을 임의로 가정하지 않는다.

기본 문법 검증은 다음과 같다.

```bash
python -m compileall app scripts rag-server/rag rag-server/scripts rag-server/main.py
```

RAG 원천 자료나 검색 로직을 변경했다면 인덱스를 다시 빌드하고 `/api/v1/health`의 `rag` 값을 확인한다.

```bash
cd rag-server && python -m scripts.build_index
```

데이터 관련 변경은 필요할 때 개발 DB에서 다음 순서로 검증한다.

```bash
python -m scripts.seed_data
uvicorn app.main:app --reload
```

그 뒤 `/docs`에서 endpoint, request/response schema, 상태코드를 확인한다.

## 12. AI Collaboration Principles

- AI가 생성한 SQL 조건과 ORM query를 개발자가 직접 검토할 수 있는 형태로 작성한다.
- 관련 없는 도메인을 대규모 리팩터링하지 않는다.
- 외부 AI가 실패해도 서비스의 fallback 동작을 고려한다.
- 데이터에 존재하지 않는 사실을 코드나 문서에서 만들어내지 않는다.
- 현재 구현의 보안상 한계와 프로젝트 요구사항을 혼동하지 않는다.
- 변경 결과를 설명할 때 수정 파일, API 변화, 데이터 영향, 검증 결과를 함께 요약한다.
