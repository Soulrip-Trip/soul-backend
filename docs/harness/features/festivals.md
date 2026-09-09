# Festivals Domain Guide

축제는 `Location`의 기본 정보와 `FestivalSchedule`의 실제 일정을 결합하는 도메인이다.

## Critical Rule

`createdtime`과 `modifiedtime`은 행사의 시작/종료일이 아니다.

실제 일정은 다음 데이터만 사용한다.

```text
FestivalSchedule.start_date
FestivalSchedule.end_date
```

## Related Files

```text
app/routers/festivals.py
app/schemas/festival.py
app/db/models.py
data/festival_schedules.json
app/services/importer.py
```

캘린더와 특정 날짜 조회는 동일한 날짜 기준을 사용해야 한다.
