---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "app/core/**/*.py"
---

# Configuration Rules

환경설정은 `Settings`를 단일 진입점으로 사용한다.

- 새 secret은 코드에 기본 실제값을 넣지 않는다.
- 새 환경변수를 추가하면 `.env.example`과 README를 함께 갱신한다.
- `cors_origins`는 쉼표 구분 문자열과 list 입력을 처리하는 현재 validator 흐름을 유지한다.
- `api_prefix`를 변경하지 않는다. 변경이 필요하면 프론트엔드 base URL과 모든 문서를 함께 갱신한다.
- AI provider 설정은 Chatbot과 AI Insight의 사용처를 구분한다.
