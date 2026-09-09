---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "app/services/chat_service.py,app/services/ai_insight_service.py,app/routers/chat.py,app/routers/ai_insights.py"
---

# AI Integration Rules

Soulrip Backend에는 서로 다른 두 AI 흐름이 있다.

## Chatbot

- Gemini를 사용한다.
- 먼저 DB에서 관련 장소, 축제, 게시글을 검색한다.
- 검색 문맥만 근거로 답하도록 system instruction을 유지한다.
- 다국어 질문은 검색을 위해 한국어 키워드로 변환할 수 있다.
- API 키가 없거나 요청이 실패하면 검색 기반 fallback을 반환한다.
- `used_ai=false`가 정상적인 fallback 상태라는 점을 유지한다.

## AI Insight

- OpenAI를 사용한다.
- 저장된 장소와 축제 데이터를 입력으로 사용한다.
- 지정된 JSON Schema를 유지한다.
- 응답의 `image_url`이 입력 데이터의 허용 URL 집합에 포함되는지 검증한다.
- 모델이 출력하지 않은 값을 백엔드가 추측해서 보완하지 않는다.

두 기능의 provider, prompt, failure policy를 서로 섞지 않는다.
