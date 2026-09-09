# Chatbot Domain Guide

지역 정보 챗봇은 Gemini를 단독 지식원으로 사용하지 않는다.

## Flow

```text
질문
↓
필요 시 한국어 검색어 변환
↓
Location / Post / FestivalSchedule 검색
↓
ChatSource + Context 생성
↓
Gemini 호출
↓
답변 또는 fallback
```

## Invariants

- 데이터에 없는 영업시간, 가격, 날짜를 추측하지 않는다.
- Source의 장소명은 저장된 표기를 유지한다.
- 최근 history는 제한된 범위만 전달한다.
- Gemini key가 없으면 검색 결과 기반 응답을 반환한다.
- 외부 API 오류를 전체 `/chat` 실패로 만들지 않는 현재 fallback을 우선 보존한다.
