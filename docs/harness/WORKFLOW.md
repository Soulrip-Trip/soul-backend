# Backend Development Workflow

## Feature Development

```text
요구사항
  ↓
API 계약 정의
  ↓
기존 유사 구현 탐색
  ↓
Router / Schema / Service / Model 영향 분석
  ↓
Frontend 영향 분석
  ↓
최소 변경 구현
  ↓
오류 / 빈 상태 / 외부 API 실패 검증
  ↓
문법 / Swagger 검증
  ↓
README / Harness 동기화
```

## Bugfix

버그는 화면 증상만 보고 Router를 수정하지 않는다. 요청 payload, Schema validation, DB 상태, query, serializer, Frontend 기대값을 순서대로 좁혀 실제 원인을 찾는다.

## AI Feature

AI 기능은 항상 다음 두 층을 분리해 생각한다.

```text
Deterministic Layer
DB 검색 / 후보 필터 / 데이터 검증

Generative Layer
OpenAI 호출
```

생성 모델이 실패하더라도 deterministic layer가 보존되는지 확인한다.

## Data Feature

데이터 변경은 원본 → importer → model → API → frontend 전체 흐름을 확인한다. 특히 축제 날짜는 별도 일정 데이터라는 규칙을 유지한다.
