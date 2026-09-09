---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "app/services/**/*.py"
---

# Service Rules

Service 계층은 재사용 가능한 도메인 로직, 외부 API, 변환 로직을 담당한다.

- Router의 HTTP 세부사항을 Service 안으로 과도하게 끌어오지 않는다.
- DB query를 추가할 때 불필요한 N+1이나 반복 query를 확인한다.
- 외부 API 호출에는 timeout과 실패 경로가 있어야 한다.
- 외부 AI 결과는 그대로 신뢰하지 않고 기존 validation을 유지하거나 강화한다.
- `recommendation.py`의 거리 계산과 순서 결정 로직은 새로 복제하지 않고 재사용한다.
- `serializers.py`의 응답 변환 로직을 확인한 뒤 중복 serializer를 만들지 않는다.
