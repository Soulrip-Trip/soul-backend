---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "app/schemas/**/*.py"
---

# Schema Rules

Pydantic Schema는 프론트엔드와 백엔드 사이의 외부 계약이다.

- API에서 실제 사용하는 snake_case/camelCase 정책을 기존 Schema에 맞춘다.
- 필수 필드를 optional로 바꾸거나 optional 필드를 필수로 바꿀 때 하위 호환성을 확인한다.
- 리스트 응답은 기존 `items + meta` 또는 도메인별 response 구조를 우선한다.
- 입력 검증은 가능한 한 Schema 수준에서 표현한다.
- ORM 모델을 그대로 외부에 노출하기보다 필요한 필드를 Schema에 명시한다.
- AI 응답 Schema는 모델 출력 검증과 연결되어 있으므로 필드명 변경을 신중하게 한다.
