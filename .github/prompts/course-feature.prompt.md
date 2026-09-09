---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Course Feature Workflow

여행코스 작업에서는 저장 코스와 동적 추천 코스를 구분한다.

```text
app/routers/courses.py
app/schemas/course.py
app/services/recommendation.py
app/db/models.py
```

추천 후보는 좌표와 이미지 등 기존 필수 조건을 존중한다. 사용자의 district, content types, duration, transport 입력을 임의로 무시하지 않는다. 새로운 경로 최적화 알고리즘을 도입하기 전에 현재 `order_nearest` 방식으로 해결 가능한지 확인한다.
