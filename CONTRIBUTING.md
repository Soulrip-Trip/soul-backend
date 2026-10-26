# Contributing Guide

Soulrip Backend에 기여할 때 따르는 브랜치, 커밋, PR 규칙이다. AI 코딩 에이전트의 작업 규칙은 [`AGENTS.md`](AGENTS.md)를 따른다.

## 1. 브랜치 전략

```text
main ─────●───────●───────●─────────▶   항상 배포 가능한 상태 (Render 자동 배포 대상)
           \     / \     /
            feat/…   fix/…                 작업 브랜치: main에서 따서 PR로만 병합
```

- `main`은 **항상 배포 가능한 상태**로 유지한다. `main`에 병합되면 Render가 배포하므로 병합 전에 검증을 끝낸다.
- 작업은 `main`에서 새 브랜치를 따서 진행하고, **PR을 통해서만** `main`에 병합한다. `main`에 직접 push하지 않는다.
- 브랜치는 하나의 목적만 가진다. 길게 끌지 말고 작게 나눠 자주 병합한다.
- 병합이 끝난 브랜치는 삭제한다.

### 브랜치 이름

`<type>/<짧은-설명>` 형식으로 소문자와 하이픈(`-`)만 쓴다.

| type | 용도 | 예시 |
| --- | --- | --- |
| `feat` | 새 기능, 동작 개선 | `feat/chat-condition-filter` |
| `fix` | 버그 수정 | `fix/festival-date-context` |
| `hotfix` | 운영 장애 긴급 수정 (`main`에서 분기, 리뷰 후 즉시 병합) | `hotfix/chat-fallback` |
| `refactor` | 동작 변경 없는 구조 개선 | `refactor/chat-search-terms` |
| `data` | 시드·보완 데이터, importer 변경 | `data/festival-schedules` |
| `docs` | 문서, 하네스 | `docs/contributing-guide` |
| `chore` | 설정, 의존성, 배포 | `chore/render-env` |

## 2. 커밋 메시지

[Conventional Commits](https://www.conventionalcommits.org/) 형식을 따른다. 설명은 한국어로 써도 된다.

```text
<type>(<scope>): <무엇을 했는지 한 줄 요약>

- 변경 이유와 핵심 내용 (필요할 때)
```

- `type`: `feat`, `fix`, `refactor`, `docs`, `chore`, `data`, `test`
- `scope`(선택): `chat`, `eval`, `places`, `festivals`, `courses`, `community`, `records`, `insight`, `db`, `config`
- 요약은 50자 안팎, 마침표 없이 쓴다. "수정", "update"처럼 내용이 없는 메시지는 쓰지 않는다.
- 하나의 커밋은 하나의 논리적 변경만 담는다.

```text
feat(chat): 지역·유형 조건을 검색 필터로 먼저 적용
fix(festivals): 원본 modifiedtime을 행사일로 노출하지 않음
docs: 브랜치 규칙과 PR 템플릿 추가
```

## 3. Pull Request 규칙

- PR 제목도 커밋 메시지와 같은 형식으로 쓴다. 본문은 [PR 템플릿](.github/pull_request_template.md)을 채운다.
- PR은 **한 가지 목적**만 다룬다. 관련 없는 도메인을 대규모 리팩터링하지 않는다.
- 리뷰어 1명 이상의 승인을 받은 뒤 병합한다. 병합은 **Squash and merge**를 기본으로 한다.
- 병합 전에 `main`의 최신 변경을 반영(rebase 또는 merge)하고 충돌을 해결한다.

### 병합 전 확인

```bash
python -m compileall app scripts          # 문법 검증
uvicorn app.main:app --reload             # 실행 후 /docs에서 변경한 endpoint 확인
```

| 변경 내용 | 추가로 확인할 것 |
| --- | --- |
| 요청·응답 필드, endpoint | `schemas`와 프론트엔드(`api.ts`, 타입) 영향. 이미 쓰는 필드명은 이유 없이 바꾸지 않는다 |
| DB 모델, 시드 데이터 | 기존 SQLite DB와 시드에 미치는 영향, 삭제 시 댓글·좋아요·일정 영향 |
| 챗봇 검색·프롬프트 | `python -m scripts.chat_eval run`으로 같은 dev 평가셋 전후 비교, 나빠진 질문이 없는지 확인 (README의 RAG Evaluation) |
| 환경변수 추가 | `.env.example`, `render.yaml`, README 갱신. 값은 코드와 저장소에 넣지 않는다 |
| 구조·계약 변경 | README와 `docs/harness/` 문서 함께 갱신 |

공통 체크리스트는 [`docs/harness/VERIFICATION_CHECKLIST.md`](docs/harness/VERIFICATION_CHECKLIST.md)에 있다.

## 4. 지켜야 할 것

- **비밀값을 커밋하지 않는다.** API key, admin key, DB URL은 `.env`와 Render 환경변수로만 관리한다. `.env.example`에는 빈 값만 둔다.
- 환경변수는 `Settings`(`app/core/config.py`)를 통해 읽는다.
- 도메인 불변조건(축제 일정은 `FestivalSchedule` 기준, 익명 커뮤니티의 비밀번호 흐름, `clientId` 소유권 등)은 [`AGENTS.md`](AGENTS.md)의 규칙을 따른다.
- 외부 AI 호출이 실패해도 서비스의 fallback 응답을 유지한다.

## 5. 배포

`main`에 병합되면 Render가 `pip install -r requirements.txt && python -m scripts.seed_data` 후 서버를 재시작한다. 새 환경변수가 필요한 변경은 **병합 전에** Render 대시보드에 값을 먼저 등록한다. (`sync: false` 항목은 대시보드에서 직접 입력해야 한다.)
