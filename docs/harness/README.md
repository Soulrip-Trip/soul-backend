# Soulrip Backend Harness Engineering Guide

이 폴더와 `.github`의 커스터마이징 파일들은 Soulrip Backend에서 AI 코딩 도구가 프로젝트 구조와 비즈니스 규칙을 매번 처음부터 추론하지 않아도 되도록 만드는 하네스이다.

## Why This Structure

백엔드는 작은 API 수정도 Router, Schema, DB, Service, Frontend 계약까지 연쇄적으로 영향을 줄 수 있다. 따라서 모든 규칙을 하나의 긴 파일에 넣기보다 작업 맥락에 따라 필요한 정보만 제공하도록 계층화한다.

```text
Global     AGENTS.md + .github/copilot-instructions.md
Domain     docs/harness/features/*.md
Local      .github/instructions/*.instructions.md
Workflow   .github/prompts/*.prompt.md
```

- Global은 모든 작업에서 지켜야 하는 불변조건이다.
- Domain은 장소, 축제, 커뮤니티, 챗봇 등 기능별 지식이다.
- Local은 특정 경로를 수정할 때 필요한 코드 규칙이다.
- Workflow는 신규 API, 버그 수정, 데이터 적재 등 반복 절차이다.

## Repository Placement

이 팩의 내용 전체를 `soulrip-backend` 저장소 루트에 복사한다.

```text
soulrip-backend/
├─ README.md                 # 이 팩의 버전으로 교체
├─ AGENTS.md
├─ .github/
│  ├─ copilot-instructions.md
│  ├─ instructions/
│  └─ prompts/
├─ docs/
│  └─ harness/
├─ app/
├─ data/
├─ scripts/
└─ requirements.txt
```

이번 팩은 기존 Backend README를 **Soulrip 전체 풀스택 서비스 관점의 README**로 교체하는 것을 전제로 한다.

## Context Loading Strategy

### Global Context

`AGENTS.md`와 `.github/copilot-instructions.md`는 API 계약, 데이터 불변조건, AI provider 구분 등 저장소 전체 규칙을 정의한다.

### Local Context

경로별 instruction은 다음과 같이 적용한다.

```text
app/routers/**       → Router Rules
app/schemas/**       → Schema Rules
app/db/**            → Database Rules
app/services/**      → Service Rules
app/core/**          → Configuration Rules
scripts/**           → Data Import Rules
```

### Domain Context

특정 기능을 작업할 때는 `features` 문서를 함께 참고한다.

```text
places.md
festivals.md
courses.md
community.md
travel-records.md
chatbot.md
ai-insights.md
data-import.md
```

### Workflow Context

반복되는 작업은 `.github/prompts`의 prompt file로 표준화한다.

예시는 다음과 같다.

```text
new-api
bugfix
place-feature
festival-feature
course-feature
community-feature
chatbot-feature
ai-insight-feature
travel-record-feature
data-import
database-change
refactor
review
deploy-check
```

## Maintenance Principles

1. 일반적인 FastAPI 문법보다 Soulrip에만 해당하는 규칙을 우선 기록한다.
2. 같은 규칙을 여러 문서에 복사하지 않는다.
3. 실패 사례가 반복될 때 규칙을 추가한다.
4. API 계약이 변경되면 Frontend 영향 범위를 함께 기록한다.
5. 도메인 규칙이 변경되면 같은 PR에서 하네스 문서를 갱신한다.
6. README는 프로젝트 소개와 실행법을 담당하고, 상세 AI 작업 규칙은 Harness 문서에 둔다.
