---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip New API Workflow

새 API 기능을 다음 순서로 구현한다.

1. 사용자 요구를 HTTP method, path, request, response, 오류 상태로 구조화한다.
2. 유사한 기존 Router와 Schema를 찾는다.
3. 프론트엔드가 소비할 계약과 하위 호환성을 확인한다.
4. 필요한 Model/Service 변경 여부를 구분한다.
5. 최소 변경 계획을 먼저 제시한다.
6. Router → Schema → Service/Model 순으로 구현한다.
7. 정상 응답, 빈 결과, 잘못된 입력, 없는 리소스의 동작을 확인한다.
8. `python -m compileall app scripts`로 문법을 검증한다.
9. API 계약이 바뀌면 README와 관련 하네스 문서를 갱신한다.

관련 없는 파일은 수정하지 않는다.
