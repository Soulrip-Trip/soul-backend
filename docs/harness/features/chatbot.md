# Chatbot Domain Guide

지역 정보 챗봇은 LLM(OpenAI)을 단독 지식원으로 사용하지 않는다.

## Flow

```text
질문
↓
필요 시 한국어 검색어 변환
↓
검색어 추출 (DB에 있는 단어만) + 지역·유형 조건 추출 (지시어뿐이면 이전 대화의 지역 승계)
↓
조건 필터 → 검색어 순위 → Location / Post / FestivalSchedule 검색
↓
ChatSource + Context 생성
↓
OpenAI 호출
↓
답변 또는 fallback
```

## Invariants

- 데이터에 없는 영업시간, 가격, 날짜를 추측하지 않는다.
- 행사 일정은 `FestivalSchedule`만 근거로 한다. 원본 `modifiedtime`을 `축제일`로 컨텍스트에 넣지 않고, 일정이 없으면 "저장된 데이터에 없음"으로 표기한다.
- 사용자가 말한 지역·유형 조건은 검색 필터로 먼저 적용한다. 조건에 맞는 장소가 없을 때만 조건을 완화하고 그 사실을 컨텍스트에 남긴다.
- 장소의 분위기·혼자 가기 좋음 같은 특성은 데이터에 없으면 말하지 않도록 `_system_instruction`의 규칙을 유지한다.
- Source의 장소명은 저장된 표기를 유지한다.
- 최근 history는 제한된 범위만 전달한다.
- OpenAI key가 없으면 검색 결과 기반 응답을 반환한다.
- 외부 API 오류를 전체 `/chat` 실패로 만들지 않는 현재 fallback을 우선 보존한다.

## Evaluation

챗봇 검색·프롬프트를 바꿀 때는 `scripts/chat_eval`로 전후를 같은 평가셋으로 측정한다. 사용법과 지표는 README의 RAG Evaluation을 따른다.

- 평가셋(`data/eval/chat_eval_set.json`)은 `soulrip.db` 실데이터가 정답이다. 데이터에 없는 사실을 정답으로 쓰지 않는다.
- 개선 중에는 `dev`만 쓰고 `holdout`은 최종 검증에서만 쓴다. 질문을 보고 프롬프트를 맞추지 않는다.
- `chat_service.build_chat_context()`와 `_system_instruction()`은 평가 하네스가 사용한다. 시그니처를 바꾸면 `scripts/chat_eval/target.py`와 `__main__.py`도 확인한다.
- 검색·프롬프트를 바꾼 뒤에는 같은 dev로 재측정하고 `compare`의 "나빠진 질문" 목록이 비었는지 확인한다. LLM 채점 지표는 같은 코드에서도 몇 p 흔들리므로(노이즈) 검색 지표처럼 결정적인 지표를 우선 본다.
- 개선 전후 수치와 원인 분석은 README의 RAG Evaluation(5~9절)에 있다. 남은 문제: 사용자 표현을 그대로 되풀이하는 추천 답변, 계획형 입력의 시각 채우기, 장소 별칭(`남산타워`)·번역 불일치로 인한 검색 실패.
