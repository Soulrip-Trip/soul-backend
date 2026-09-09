---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "data/**/*.json"
---

# Data File Rules

`data/`의 JSON은 백엔드 로직이 의존하는 보완 데이터이다.

- 축제 일정은 `contentId`, `startDate`, `endDate`를 기준으로 연결한다.
- 날짜 형식은 `YYYY-MM-DD`를 유지한다.
- 실제 근거가 없는 일정을 임의로 작성하지 않는다.
- `festival_schedules.example.json`과 실제 파일의 구조를 동기화한다.
- 데이터 변경은 관련 API의 캘린더, 날짜 필터, 챗봇 검색에 영향을 줄 수 있다.
