---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Backend Deploy Check

배포 전 다음 항목을 검증한다.

1. `requirements.txt`에 필요한 dependency가 존재한다.
2. `.env.example`의 변수 목록과 `Settings`가 일치한다.
3. 실제 secret이 저장소에 포함되지 않았다.
4. 운영 Frontend origin이 CORS에 허용되어 있다.
5. `python -m compileall app scripts`가 통과한다.
6. `/api/v1/health`와 `/docs`가 실행 환경에서 노출되는지 확인한다.
7. AI key가 없을 때 챗봇 fallback과 AI Insight 오류가 예상대로 동작한다.
8. SQLite 파일 영속성 또는 운영 DB 정책을 확인한다.
