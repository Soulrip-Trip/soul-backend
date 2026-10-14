# Chatbot Domain Guide

지역 정보 챗봇은 Gemini를 단독 지식원으로 사용하지 않는다. Soulrip DB 검색 결과와 RAG(서울관광 실태조사·서울시 공공데이터) 근거만으로 답한다.

## Flow

```text
질문 + history + language
↓
history 정규화 (현재 질문 중복·앞쪽 assistant 제거, 최근 10개, 메시지당 800자)
↓
응답 캐시 조회 (언어·질문·맥락)
↓
필요 시 한국어 검색어 변환 (캐시)
↓
asyncio.gather(
  Location / Post / FestivalSchedule 검색 (to_thread),
  rag_service.search → top-k 근거 (embedded | remote | off)
)
↓
ChatSource + Context 생성 (근거마다 연도·대상·확정/잠정·위치 라벨, 7,000자 상한)
↓
Gemini 호출 (공유 AsyncClient, Semaphore)
↓
답변(캐시 저장) 또는 fallback
```

## Files

- `app/services/chat_service.py`: 흐름 전체, history 정규화, Context 조립, fallback
- `app/services/rag_service.py`: RAG 모드별 검색, 실패 시 빈 결과
- `app/services/gemini_client.py`: Gemini 호출, 동시성 제한
- `rag-server/rag/retriever.py`: BM25 + 메타데이터 가중치 검색
- `rag-server/data/manifest.json`: 원천 자료 메타데이터

## Invariants

- 데이터에 없는 영업시간, 가격, 날짜를 추측하지 않는다.
- 축제 날짜는 `FestivalSchedule`(또는 RAG 문화행사 기간)만 사용한다. `source_modified_at`을 날짜로 Context에 넣지 않는다.
- Source의 장소명은 저장된 표기를 유지한다.
- 최근 history는 최대 10개 메시지만 전달한다.
- Gemini key가 없으면 검색 결과 기반 응답을 반환한다(`usedAi=false`).
- 외부 API·RAG 오류를 전체 `/chat` 실패로 만들지 않는다. RAG 실패 시 DB 검색만으로 답한다.
- 응답 계약 `answer`, `sources`, `suggestions`, `usedAi`를 보존한다. `ChatSource.url`은 추가 필드다.

## RAG Invariants

- RAG는 서버 내부에서만 동작한다. 프론트엔드가 RAG 서버를 호출하거나 키를 갖게 하지 않는다.
- 요청마다 원천 자료(PDF·XLSX)를 읽거나 전체 자료를 프롬프트에 넣지 않는다. 오프라인 빌드한 인덱스에서 top-k 근거만 전달한다.
- 실태조사 근거에는 연도·조사 대상·확정/잠정 라벨을 붙인다. 2026 외국인 자료는 잠정치이며, 답변에서도 잠정치임을 밝히도록 system prompt를 유지한다.
- 서로 다른 연도·대상의 수치를 합치지 않도록 하는 규칙을 완화하지 않는다.
- 응답자 원자료(`rag-server/data/raw`), 설문지, 코드북은 색인하지 않는다. 바꾸려면 `manifest.json`의 `index`, `exclude_reason`을 함께 수정한다.
- 원천 자료를 바꾸면 `python -m scripts.build_index`(rag-server)로 인덱스를 다시 빌드하고 `index/`를 커밋한다.
