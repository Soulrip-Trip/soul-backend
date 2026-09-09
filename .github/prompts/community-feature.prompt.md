---
mode: agent
description: Soulrip Backend 반복 작업 프롬프트이다
---

# Soulrip Community Feature Workflow

커뮤니티 기능은 로그인 없는 익명 사용자를 전제로 한다.

```text
app/routers/posts.py
app/schemas/post.py
app/db/models.py
```

게시글 CRUD, 비밀번호 검증, 댓글, 좋아요가 서로 연결되어 있다. 변경 시 `views`, `likes_count`, comment count, `tags_json`, 비밀번호 확인 흐름의 일관성을 확인한다. 현재 비밀번호 저장 방식의 보안 한계는 인정하되 요청 없이 인증 시스템 전체를 교체하지 않는다.
