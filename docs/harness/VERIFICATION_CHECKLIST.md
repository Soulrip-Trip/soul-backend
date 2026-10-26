# Backend Verification Checklist

## Code

- [ ] 변경 파일의 책임이 기존 계층과 맞는가.
- [ ] 새 import와 dependency가 실제로 필요한가.
- [ ] `python -m compileall app scripts`가 통과하는가.

## API

- [ ] method와 path가 기존 naming과 일치하는가.
- [ ] request Schema가 실제 입력을 검증하는가.
- [ ] response model과 실제 반환값이 일치하는가.
- [ ] 404와 사용자 입력 오류가 구분되는가.
- [ ] pagination과 정렬 기준이 유지되는가.

## Database

- [ ] 새 query가 불필요한 반복 조회를 만들지 않는가.
- [ ] nullable 데이터가 안전하게 처리되는가.
- [ ] 관계 데이터 삭제 영향이 확인되었는가.
- [ ] 기존 SQLite DB에 migration이 필요한 변경인지 확인했는가.

## Data

- [ ] 축제 일정이 `FestivalSchedule`을 사용하고 있는가.
- [ ] 원본 JSON의 생성/수정 시각을 축제 날짜로 사용하지 않았는가.
- [ ] importer 매핑과 Model 필드가 일치하는가.

## AI

- [ ] Chatbot은 OpenAI와 검색 기반 fallback을 유지하는가.
- [ ] AI Insight는 OpenAI와 JSON Schema 검증을 유지하는가.
- [ ] 데이터 밖 사실을 추측하도록 prompt가 완화되지 않았는가.
- [ ] 외부 API timeout/오류가 사용자 요청 전체를 예상치 않게 깨뜨리지 않는가.
- [ ] Chatbot 검색·프롬프트를 바꿨다면 `python -m scripts.chat_eval run`으로 같은 dev 평가셋 전후를 비교했고, 나빠진 질문(compare 결과)을 확인했는가.
- [ ] 평가셋을 수정했다면 `python -m scripts.chat_eval check`가 통과하는가.

## Full-stack

- [ ] 응답 필드 변경이 Frontend `api.ts`와 타입에 미치는 영향을 확인했는가.
- [ ] CORS 변경이 Frontend 배포 origin과 일치하는가.
- [ ] README와 Harness가 현재 코드와 일치하는가.
