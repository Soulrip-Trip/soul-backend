---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Festival Feature Workflow

축제 기능은 `Location(content_type_id=15)`과 `FestivalSchedule`의 결합으로 이해한다.

1. 목록/상세인지 일정/캘린더 기능인지 구분한다.
2. 실제 일정은 `FestivalSchedule`만 사용한다.
3. 원본 `createdtime`, `modifiedtime`을 행사 날짜로 사용하지 않는다.
4. `festival_schedules.json`과 importer 영향 범위를 확인한다.
5. 관리자 일정 API 변경 시 `X-Admin-Key` 검증을 확인한다.
6. 캘린더, on-date, 목록 필터가 동일 날짜 의미를 사용하는지 검증한다.
