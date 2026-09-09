---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Place Feature Workflow

장소 기능을 수정할 때 다음 파일을 우선 탐색한다.

```text
app/routers/places.py
app/schemas/location.py
app/db/models.py
app/services/serializers.py
app/services/recommendation.py
```

`Location` 중심 모델, `content_type_id`, nullable 좌표/이미지, 검색/페이지네이션 계약을 유지한다. 주변 장소나 거리 기능에서는 기존 haversine 계산을 재사용한다. 새 필터를 추가하면 목록, 지도, 챗봇 검색에서 의미가 충돌하지 않는지 확인한다.
