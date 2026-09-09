---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Backend Review Workflow

변경사항을 다음 관점에서 검토한다.

- API 하위 호환성이 깨지지 않았는가.
- Pydantic Schema와 실제 반환값이 일치하는가.
- SQLAlchemy query가 의도한 필터/정렬/페이지네이션을 수행하는가.
- N+1 또는 불필요한 반복 query가 추가되지 않았는가.
- 축제 일정의 데이터 출처가 올바른가.
- AI가 데이터 밖 내용을 생성하도록 완화되지 않았는가.
- 외부 AI 실패 시 fallback이 유지되는가.
- secret이 코드 또는 로그에 노출되지 않는가.
- 다른 clientId 또는 다른 게시글의 권한을 침범하지 않는가.
- 관련 README/하네스가 코드와 동기화되어 있는가.

중요도 순으로 문제를 정리하고 가능하면 파일과 원인 단위를 함께 제시한다.
