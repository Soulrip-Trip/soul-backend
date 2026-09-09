---
description: Soulrip Backend 경로별 작업 규칙이다
applyTo: "render.yaml,requirements.txt,.env.example"
---

# Deployment Rules

배포 관련 파일은 개발 환경과 운영 환경의 계약이다.

- dependency 추가 시 `requirements.txt`를 갱신한다.
- secret은 `render.yaml`이나 `.env.example`에 실제 값으로 넣지 않는다.
- 운영 CORS origin은 실제 프론트엔드 배포 주소와 일치해야 한다.
- 시작 명령이나 Python 버전을 바꾸면 Render 배포 영향 범위를 확인한다.
- SQLite 파일 영속성의 한계를 인지하고 운영 DB 변경 시 문서에 명시한다.
