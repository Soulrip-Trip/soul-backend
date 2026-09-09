---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Backend Bugfix Workflow

버그를 수정할 때 증상만 가리는 패치를 만들지 않는다.

1. 재현 조건과 기대 동작을 정리한다.
2. Router, Schema, Service, Model, Data 중 실제 원인 계층을 찾는다.
3. 프론트엔드 요청 payload와 응답 기대값을 함께 확인한다.
4. 원인과 가장 가까운 최소 변경을 적용한다.
5. 동일 도메인의 다른 endpoint에 같은 문제가 있는지 확인한다.
6. DB 데이터가 원인이라면 코드 결함과 데이터 결함을 구분한다.
7. 외부 AI 오류라면 fallback 경로까지 확인한다.
8. 문법 검증과 관련 API 수동 검증을 수행한다.
