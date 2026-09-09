# Full-stack Contract Guide

Frontend와 Backend는 별도 저장소이지만 하나의 제품 계약을 공유한다.

## Backend Contract Changes

다음 변경은 Frontend 확인이 필요하다.

- endpoint path 또는 method 변경
- request body 필드 변경
- query parameter 이름 변경
- response 필드 이름/타입 변경
- enum 값 변경
- 날짜 형식 변경
- pagination 구조 변경
- 오류 상태코드 변경

## Frontend Reference

```text
https://github.com/skyblue1232/soulrip-frontend
```

Frontend에서는 `src/services/api.ts`와 `src/types`를 우선 확인하고 관련 View/Component까지 추적한다.
