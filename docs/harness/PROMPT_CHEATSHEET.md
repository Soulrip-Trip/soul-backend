# Prompt Cheatsheet

작업 목적에 맞는 prompt file을 선택한다.

| Task | Prompt |
| --- | --- |
| 새 API | `new-api.prompt.md` |
| 버그 수정 | `bugfix.prompt.md` |
| 장소 | `place-feature.prompt.md` |
| 축제 | `festival-feature.prompt.md` |
| 코스 | `course-feature.prompt.md` |
| 커뮤니티 | `community-feature.prompt.md` |
| 챗봇 | `chatbot-feature.prompt.md` |
| AI Insight | `ai-insight-feature.prompt.md` |
| 여행 기록 | `travel-record-feature.prompt.md` |
| 데이터 적재 | `data-import.prompt.md` |
| DB 변경 | `database-change.prompt.md` |
| 리팩터링 | `refactor.prompt.md` |
| 코드 리뷰 | `review.prompt.md` |
| 배포 전 점검 | `deploy-check.prompt.md` |

## Example Request

```text
/soulrip-backend-new-api

places API에 district 여러 개를 받을 수 있는 필터를 추가한다.
기존 단일 district 호출과 하위 호환성을 유지하고 Frontend 영향 범위까지 확인한다.
```

Prompt file이 slash command 이름으로 어떻게 표시되는지는 사용하는 VS Code/Copilot 버전에 따라 달라질 수 있다. 파일 이름과 설명을 기준으로 선택한다.
