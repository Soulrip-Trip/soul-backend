---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Travel Record Workflow

여행 기록은 회원 계정이 아니라 `clientId` 기반 소유권을 사용한다.

1. list/detail/update/delete에서 동일한 소유권 기준을 사용하는지 확인한다.
2. 다른 clientId의 레코드가 노출되지 않는지 확인한다.
3. request/response Schema 변경 시 프론트엔드 localStorage 흐름을 확인한다.
4. DB 필드 추가 시 기존 기록과 nullable/default 호환성을 고려한다.
