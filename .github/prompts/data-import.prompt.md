---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Data Import Workflow

새 서울 공공데이터 파일 또는 필드를 적재할 때 다음 순서로 진행한다.

1. 실제 원본 JSON의 key와 값 형태를 확인한다.
2. 기존 `CONTENT_FILES` 매핑에 포함되는지 확인한다.
3. Model에 저장할 필요가 있는 값인지 판단한다.
4. importer의 정규화 함수를 재사용한다.
5. 신규/기존 `content_id`의 imported/updated 동작을 확인한다.
6. 파일 누락과 잘못된 row를 어떻게 처리할지 기존 정책에 맞춘다.
7. 축제 일정 데이터라면 일반 Location import와 분리한다.
8. 시드 후 대표 endpoint로 결과를 검증한다.
