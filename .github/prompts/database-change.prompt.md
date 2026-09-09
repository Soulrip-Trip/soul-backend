---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Database Change Workflow

DB 모델 변경 전 다음을 반드시 확인한다.

1. 변경되는 table, column, relationship을 나열한다.
2. 기존 `soulrip.db`와의 호환성을 확인한다.
3. 단순 `create_all`만으로 기존 table 구조가 변경되지 않는 경우 migration 필요성을 명시한다.
4. importer와 Schema 영향을 확인한다.
5. nullable, default, unique, index, foreign key 결정을 근거와 함께 설명한다.
6. 데이터 유실 가능성이 있는 자동 삭제/재생성은 수행하지 않는다.
