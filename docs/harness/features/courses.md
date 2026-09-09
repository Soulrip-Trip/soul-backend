# Courses Domain Guide

Soulrip의 코스에는 두 종류가 있다.

1. 원본 공공데이터의 여행코스이다.
2. 현재 사용자 조건을 기반으로 동적으로 만드는 추천 코스이다.

동적 추천은 좌표가 존재하는 후보를 선택하고 기존 `order_nearest` 로직으로 이동 순서를 구성한다.

추천 알고리즘 변경 시 정확도만 보지 않고 API 응답의 `estimated_hours`, `transport`, `stops` 계약과 계산 비용을 함께 확인한다.
