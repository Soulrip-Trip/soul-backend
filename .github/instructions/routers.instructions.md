---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "app/routers/**/*.py"
---

# Router Rules

Router는 HTTP 계약과 dependency를 담당한다.

- prefix와 tag는 기존 도메인 naming을 따른다.
- DB Session은 `Depends(get_db)`를 사용한다.
- request body는 가능한 한 Pydantic Schema로 받는다.
- response model을 명시하여 프론트엔드 계약을 고정한다.
- 404, 400, 403, 409, 5xx 등 상태코드는 오류 의미에 맞게 구분한다.
- Router 내부에 외부 AI API 호출 코드를 새로 직접 추가하지 않는다. 기존 Service를 확장한다.
- 복잡한 직렬화가 반복되면 기존 `app/services/serializers.py` 패턴을 검토한다.
- query parameter의 default, 최소/최대값을 변경할 때 프론트엔드 페이지네이션 영향을 확인한다.
- 새 Router 파일을 추가하면 `app/main.py` 등록을 함께 확인한다.
