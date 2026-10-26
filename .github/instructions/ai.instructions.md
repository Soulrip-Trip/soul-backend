---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "app/services/chat_service.py,app/services/rag_service.py,app/services/openai_client.py,app/services/ai_insight_service.py,app/routers/chat.py,app/routers/ai_insights.py,rag-server/**"
---

# AI Integration Rules

Soulrip Backend에는 서로 다른 두 AI 흐름이 있다.

## Chatbot

- OpenAI를 사용한다.
- 먼저 DB에서 관련 장소, 축제, 게시글을 검색하고, 동시에 RAG(서울관광 실태조사·공공데이터)에서 top-k 근거를 검색한다.
- RAG 근거의 연도·조사 대상·확정/잠정 라벨을 Context에 유지한다. 2026 외국인 자료는 잠정치다.
- 요청마다 원천 자료를 읽거나 전체 자료를 프롬프트에 넣지 않는다. 인덱스는 오프라인 빌드, 기동 시 1회 로드한다.
- RAG 실패·인덱스 누락은 빈 근거로 처리하고 DB 검색만으로 답한다.
- 검색 문맥만 근거로 답하도록 system instruction을 유지한다.
- 다국어 질문은 검색을 위해 한국어 키워드로 변환할 수 있다.
- API 키가 없거나 요청이 실패하면 검색 기반 fallback을 반환한다.
- `usedAi=false`가 정상적인 fallback 상태라는 점을 유지한다.
- OpenAI 호출은 `openai_client.generate_text`(공유 AsyncClient, 동시성 제한)를 사용한다.

## AI Insight

- OpenAI를 사용한다.
- 저장된 장소와 축제 데이터를 입력으로 사용한다.
- 지정된 JSON Schema를 유지한다.
- 응답의 `image_url`이 입력 데이터의 허용 URL 집합에 포함되는지 검증한다.
- 모델이 출력하지 않은 값을 백엔드가 추측해서 보완하지 않는다.
- OpenAI 클라이언트는 첫 요청에서 만든다. 키가 없을 때 앱 기동이 실패하지 않고 해당 API만 503을 반환해야 한다.
- 설정 누락·데이터 없음·연결 실패는 503, 응답 형식 오류는 502, 한도 초과는 429로 구분한다.

두 기능의 provider, prompt, failure policy를 서로 섞지 않는다.
