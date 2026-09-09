# Places Domain Guide

장소 도메인의 중심 모델은 `Location`이다.

## Responsibilities

- 목록 검색
- 상세 조회
- 지도 표시
- 주변 장소 검색
- 카테고리/자치구 필터

## Invariants

- `content_id`는 공공데이터 식별자이다.
- `content_type_id`와 `content_type` 매핑을 유지한다.
- 이미지, 설명, 위도, 경도는 없을 수 있다.
- 거리 계산은 좌표가 있는 경우에만 수행한다.
- 검색 결과 정렬은 기존 featured, solo score, source 수정일 등의 의미를 확인한 뒤 변경한다.
