---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "scripts/**/*.py,app/services/importer.py"
---

# Data Import Rules

데이터 적재 로직은 원본 JSON과 DB 사이의 계약이다.

- 원본 파일명을 임의로 바꾸지 않는다.
- `CONTENT_FILES`의 contentTypeId와 한글 유형 매핑을 유지한다.
- 값 변환은 기존 `_empty_to_none`, `_to_float`, `_to_int`, 날짜 파서 등을 우선 재사용한다.
- 동일 `content_id`가 존재하면 update하는 현재 동작을 깨뜨리지 않는다.
- URL 정규화 규칙을 임의로 제거하지 않는다.
- 축제 일정은 반드시 `festival_schedules.json`을 별도로 처리한다.
- 잘못된 일정 행은 전체 import를 중단하기보다 기존 skip 정책과 통계를 고려한다.
- importer 변경 후 imported/updated/skipped 의미가 유지되는지 확인한다.
