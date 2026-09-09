---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "app/db/**/*.py"
---

# Database Rules

DB 계층은 SQLAlchemy와 SQLite를 사용한다.

- `Location`은 관광 데이터의 중심 엔티티이다.
- 외부 데이터의 `content_id`는 안정적인 식별자로 유지한다.
- index, unique, foreign key 의미를 변경할 때 기존 DB와 importer 영향을 확인한다.
- relationship 추가/수정 시 cascade와 삭제 영향을 확인한다.
- 새 필드가 원본 JSON에서 채워지는 값이라면 importer도 함께 갱신한다.
- 새 필드가 API에 노출된다면 관련 Schema와 Serializer도 함께 갱신한다.
- SQLite에 바로 적용하기 어려운 migration이 필요한 변경은 자동으로 숨기지 않고 migration 필요성을 명시한다.
