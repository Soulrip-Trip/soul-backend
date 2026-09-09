# Project Context

Soulrip은 서울 공공 관광 데이터를 활용하여 혼자 여행하는 사용자의 탐색, 계획, 공유를 연결하는 서비스이다.

## Core Flow

```text
Discover Solo → Plan Solo → Share Solo
```

Backend 관점에서는 다음과 같이 연결된다.

- Discover는 장소, 축제, 코스 조회 API가 담당한다.
- Plan은 코스 추천, 챗봇, AI Insight가 담당한다.
- Share는 익명 커뮤니티와 여행 기록이 담당한다.

## Product Constraints

- 서울 지역 데이터를 중심으로 한다.
- 회원가입이 없는 사용자 흐름이 존재한다.
- 데이터에 없는 관광 정보를 AI가 임의로 보완하지 않는다.
- Frontend와 Backend는 별도 저장소이지만 하나의 제품 계약으로 동작한다.
- 개발 기간 표기는 특정 일수 대신 `n일`로 관리한다.

## Data Categories

```text
관광지
문화시설
축제·공연·행사
여행코스
레포츠
숙박
쇼핑
음식점(데이터가 있을 경우)
```
