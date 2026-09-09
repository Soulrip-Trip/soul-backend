---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "app/main.py"
---

# Application Entry Rules

`app/main.py`는 앱 조립 지점이다.

- 비즈니스 로직을 추가하지 않는다.
- CORS 설정은 `Settings` 값을 사용한다.
- 새 Router를 추가할 때 기존 `settings.api_prefix`를 동일하게 적용한다.
- 앱 title, version, description 변경은 외부 Swagger 표현에 영향을 준다는 점을 고려한다.
- DB 초기화 방식 변경은 배포 환경의 SQLite 동작에 영향을 줄 수 있으므로 명시적으로 검토한다.
