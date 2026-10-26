# Chatbot Domain Guide

지역 정보 챗봇은 LLM(OpenAI)을 단독 지식원으로 사용하지 않는다. Soulrip DB 검색 결과와 RAG(서울관광 실태조사·서울시 공공데이터) 근거만으로 답한다.

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
  Location / Post / FestivalSchedule 검색 (to_thread)
    └ 검색어 추출(DB에 있는 단어만) → 지역·유형 조건 추출(지시어뿐이면 이전 대화의 지역 승계)
      → 조건 필터 → 역빈도 순위,
  rag_service.search → top-k 근거 (embedded | remote | off)
)
↓
ChatSource + Context 생성 (근거마다 연도·대상·확정/잠정·위치 라벨, 7,000자 상한)
↓
OpenAI 호출 (공유 AsyncClient, Semaphore)
↓
답변(캐시 저장) 또는 fallback
```

## Files

- `app/services/chat_service.py`: 흐름 전체, history 정규화, Context 조립, fallback
- `app/services/rag_service.py`: RAG 모드별 검색, 실패 시 빈 결과
- `app/services/openai_client.py`: OpenAI 호출, 동시성 제한
- `rag-server/rag/retriever.py`: BM25 + 메타데이터 가중치 검색
- `rag-server/data/manifest.json`: 원천 자료 메타데이터

## Invariants

- 데이터에 없는 영업시간, 가격, 날짜를 추측하지 않는다.
- 축제 날짜는 `FestivalSchedule`(또는 RAG 문화행사 기간)만 사용한다. `source_modified_at`을 날짜로 Context에 넣지 않는다.
- 사용자가 말한 지역·유형 조건은 검색 필터로 먼저 적용한다. 조건에 맞는 장소가 없을 때만 조건을 완화하고 그 사실을 컨텍스트에 남긴다.
- 장소의 분위기·혼자 가기 좋음 같은 특성은 데이터에 없으면 말하지 않도록 `SYSTEM_PROMPT`의 규칙을 유지한다.
- Source의 장소명은 저장된 표기를 유지한다.
- 최근 history는 최대 10개 메시지만 전달한다.
- OpenAI key가 없으면 검색 결과 기반 응답을 반환한다(`usedAi=false`).
- 외부 API·RAG 오류를 전체 `/chat` 실패로 만들지 않는다. RAG 실패 시 DB 검색만으로 답한다.
- 응답 계약 `answer`, `sources`, `suggestions`, `usedAi`를 보존한다. `ChatSource.url`은 추가 필드다.

## RAG Invariants

- RAG는 서버 내부에서만 동작한다. 프론트엔드가 RAG 서버를 호출하거나 키를 갖게 하지 않는다.
- 요청마다 원천 자료(PDF·XLSX)를 읽거나 전체 자료를 프롬프트에 넣지 않는다. 오프라인 빌드한 인덱스에서 top-k 근거만 전달한다.
- 실태조사 근거에는 연도·조사 대상·확정/잠정 라벨을 붙인다. 2026 외국인 자료는 잠정치이며, 답변에서도 잠정치임을 밝히도록 system prompt를 유지한다.
- 서로 다른 연도·대상의 수치를 합치지 않도록 하는 규칙을 완화하지 않는다.
- 응답자 원자료(`rag-server/data/raw`), 설문지, 코드북은 색인하지 않는다. 바꾸려면 `manifest.json`의 `index`, `exclude_reason`을 함께 수정한다.
- 원천 자료를 바꾸면 `python -m scripts.build_index`(rag-server)로 인덱스를 다시 빌드하고 `index/`를 커밋한다.

## Evaluation

챗봇 검색·프롬프트를 바꿀 때는 `scripts/chat_eval`로 전후를 같은 평가셋으로 측정한다. 사용법과 지표는 README의 RAG Evaluation을 따른다.

- 평가셋(`data/eval/chat_eval_set.json`)은 `soulrip.db` 실데이터가 정답이다. 데이터에 없는 사실을 정답으로 쓰지 않는다.
- 개선 중에는 `dev`만 쓰고 `holdout`은 최종 검증에서만 쓴다. 질문을 보고 프롬프트를 맞추지 않는다.
- `chat_service.build_chat_context()`(비동기)와 `_system_instruction()`은 평가 하네스가 사용한다. 시그니처를 바꾸면 `scripts/chat_eval/target.py`도 확인한다.
- 검색·프롬프트를 바꾼 뒤에는 같은 dev로 재측정하고 `compare`의 "나빠진 질문" 목록이 비었는지 확인한다. LLM 채점 지표는 같은 코드에서도 몇 p 흔들리므로(노이즈) 검색 지표처럼 결정적인 지표를 우선 본다.
