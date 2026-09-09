---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Backend Refactor Workflow

리팩터링은 동작 보존을 전제로 한다.

1. 현재 endpoint와 응답 계약을 기록한다.
2. 중복 코드와 책임 혼재 지점을 찾는다.
3. Router/Schema/Service/DB 경계를 더 단순하게 만드는 방향만 선택한다.
4. 대규모 범용 추상화보다 반복되는 실제 패턴을 먼저 제거한다.
5. AI fallback, 데이터 일정, clientId, 비밀번호 같은 도메인 불변조건을 보존한다.
6. 변경 전후 endpoint와 문법 검증 결과를 비교한다.
