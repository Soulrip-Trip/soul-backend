---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip AI Insight Workflow

AI Insight 작업은 다음 원칙을 따른다.

1. DB에서 입력 데이터 후보를 수집한다.
2. AI에 전달하는 compact context가 실제 DB 값을 보존하는지 확인한다.
3. System Prompt에서 데이터 밖 추측 금지 원칙을 유지한다.
4. OpenAI JSON Schema를 변경하면 Pydantic Schema도 함께 확인한다.
5. 반환 이미지 URL은 입력 데이터의 URL 집합으로 검증한다.
6. 빈 데이터, API key 없음, 외부 API 오류, JSON decode 실패를 구분한다.
7. Router의 HTTP 오류 매핑이 실제 provider와 일치하는지 확인한다.
