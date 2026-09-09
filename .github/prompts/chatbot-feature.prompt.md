---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Chatbot Feature Workflow

챗봇은 AI 호출보다 검색 문맥 생성이 먼저이다.

1. 질문을 검색에 적합한 형태로 변환한다.
2. Location, Post, FestivalSchedule에서 근거 데이터를 찾는다.
3. `ChatSource`를 생성한다.
4. 최근 history와 검색 문맥을 Gemini에 전달한다.
5. 데이터 밖 사실을 추측하지 않도록 prompt 규칙을 유지한다.
6. Gemini key 없음, timeout, HTTP 오류에서 fallback 응답을 확인한다.
7. `answer`, `sources`, `suggestions`, `used_ai` 응답 계약을 유지한다.
8. 7개 언어 입력 흐름을 함께 확인한다.
