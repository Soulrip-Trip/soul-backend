# Travel Records Domain Guide

여행 기록은 로그인 계정 대신 브라우저 `clientId`로 사용자 범위를 구분한다.

## Invariants

- 목록은 해당 clientId의 기록만 반환한다.
- 상세 조회와 수정/삭제에서도 소유권을 다시 검증한다.
- request와 query의 `clientId` 위치가 endpoint마다 다를 수 있으므로 현재 Schema와 Router를 확인한다.
- clientId를 보안상 강한 사용자 인증으로 오해하지 않는다.
