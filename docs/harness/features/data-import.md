# Data Import Domain Guide

데이터 적재는 서울 공공 JSON을 `Location` 중심 구조로 정규화하는 과정이다.

## Recognized Types

```text
12 관광지
14 문화시설
15 축제공연행사
25 여행코스
28 레포츠
32 숙박
38 쇼핑
39 음식점
```

## Invariants

- 기존 `content_id`는 update한다.
- 새 `content_id`는 insert한다.
- 빈 값과 숫자 변환은 공통 helper를 사용한다.
- 이미지 URL의 HTTPS 정규화 흐름을 보존한다.
- 축제 일정 import는 일반 Location import와 분리한다.
- 잘못된 일정은 skip하고 통계에 반영하는 현재 정책을 고려한다.
