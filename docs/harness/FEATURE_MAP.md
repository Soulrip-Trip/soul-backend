# Backend Feature Map

기능 수정 시 처음 확인할 파일을 빠르게 찾기 위한 지도이다.

| Feature | Router | Schema | Service / DB |
| --- | --- | --- | --- |
| 장소 탐색 | `routers/places.py` | `schemas/location.py` | `models.Location`, `serializers.py`, `recommendation.py` |
| 축제 | `routers/festivals.py` | `schemas/festival.py` | `models.FestivalSchedule`, `data/festival_schedules.json` |
| 여행코스 | `routers/courses.py` | `schemas/course.py` | `models.CourseStop`, `recommendation.py` |
| 커뮤니티 | `routers/posts.py` | `schemas/post.py` | `Post`, `Comment`, `PostLike` |
| 여행 기록 | `routers/travel_records.py` | `schemas/travel_record.py` | `TravelRecord` |
| 챗봇 | `routers/chat.py` | `schemas/chat.py` | `chat_service.py`, `Location`, `Post`, `FestivalSchedule` |
| AI Insight | `routers/ai_insights.py` | `schemas/ai_insight.py` | `ai_insight_service.py` |
| 메타 | `routers/meta.py` | 관련 응답 Schema | `Location` 통계 query |
| 기본 Insight | `routers/insights.py` | `schemas/insight.py` | DB query |
| 데이터 적재 | - | - | `services/importer.py`, `scripts/seed_data.py` |
| 환경설정 | - | - | `core/config.py`, `.env.example` |

## Cross-repository Map

Backend 변경이 Frontend에 영향을 줄 가능성이 높은 위치는 다음과 같다.

```text
Backend Schema / Endpoint
        ↓
Frontend src/services/api.ts
        ↓
Frontend src/types
        ↓
Frontend View / Component
```

응답 필드, enum, 페이지네이션, 날짜 형식, 오류 형태를 변경할 때 이 흐름을 확인한다.
