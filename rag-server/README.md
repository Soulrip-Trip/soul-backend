# Soulrip RAG Server

서울관광 실태조사(2024·2025 확정, 2026 외국인 잠정치)와 서울시 관광 공공데이터를 **오프라인에서 한 번 색인**하고, 챗봇이 질문할 때 관련 근거 몇 개만 꺼내 주는 검색 모듈이자 API 서버다.

- 검색은 로컬 BM25 역색인이라 **요청마다 외부 API 호출·토큰 비용이 없다.**
- 인덱스는 프로세스 시작 시 **한 번만** 메모리에 올린다(≈0.12s).
- 모든 근거에 **연도·조사 대상·확정/잠정 여부·출처**가 붙어 LLM이 잠정치를 확정치처럼 말하지 않게 한다.
- 프론트엔드는 이 서버를 직접 호출하지 않는다. 백엔드 `/api/v1/chat`이 내부에서 사용한다.

## 사용 방식

| 모드 | 동작 | 언제 |
| --- | --- | --- |
| `embedded` (기본) | 백엔드가 `rag-server/index`를 자기 프로세스에 로드해 `rag.retriever`를 직접 호출 | 서비스 1개로 배포(Render) |
| `remote` | 백엔드가 이 서버의 `POST /api/v1/rag/search`를 호출 | RAG를 별도 서비스로 분리·확장 |
| `off` | RAG 미사용 | 장애 격리·비교 테스트 |

백엔드 설정은 루트 `.env`의 `RAG_MODE`, `RAG_SERVER_URL`, `RAG_API_KEY`로 바꾼다.

## 폴더 구조

```text
rag-server/
├─ data/
│  ├─ manifest.json                   # 원천 자료 메타데이터·색인 여부(아래 표)
│  ├─ reports/
│  │  ├─ 2024_domestic/               # 조사개요, 최종보고서, 설문지(색인 제외)
│  │  ├─ 2024_foreign/
│  │  ├─ 2025_domestic/               # 보고서
│  │  ├─ 2025_foreign/                # 보고서, 인포그래픽
│  │  └─ 2026_foreign_preliminary/    # (4차/8월) 잠정치 보고서
│  ├─ statistics/
│  │  ├─ 2024_domestic/ 2024_foreign/ # 통계표, 코드북(색인 제외)
│  │  ├─ 2025_domestic/ 2025_foreign/ # 통계표
│  │  └─ foreign_2019_2025/           # 통합 통계표, 코드표(색인 제외)
│  ├─ places/
│  │  ├─ attractions/                 # 서울시 관광 명소(5개 언어 중 ko만 색인)
│  │  ├─ culture_spaces/              # 서울시 문화공간 정보
│  │  ├─ culture_events/              # 서울시 문화행사 정보(종료된 행사 제외)
│  │  ├─ districts/                   # 자치구 길관광·관광지·지역특화거리 CSV
│  │  └─ tourism_analytics/           # 서울 관광지 방문자·체류·이동 CSV
│  └─ raw/                            # 응답자 원자료(SAV/XLSX) — 색인 제외, git 제외
├─ rag/
│  ├─ manifest.py     # manifest 로더, 라벨(내국인/외국인, 확정치/잠정치)
│  ├─ loaders.py      # PDF·통계표 XLSX·JSON·CSV → chunk
│  ├─ text.py         # 정규화, 한국어 토크나이저(조사 제거 단어 + bigram)
│  ├─ index.py        # BM25 역색인 빌드·저장·로드(numpy CSR)
│  ├─ retriever.py    # 질의 분석·메타데이터 가중치·하이브리드 검색
│  ├─ embeddings.py   # (선택) Gemini 임베딩
│  ├─ cache.py        # TTL 캐시
│  ├─ schemas.py      # API 요청/응답 모델
│  └─ settings.py
├─ scripts/build_index.py
├─ index/             # 빌드 결과(커밋 대상): chunks.jsonl.gz, vocab.json, bm25.npz, meta.json
├─ main.py            # 검색 API (remote 모드)
└─ requirements.txt
```

## 색인 대상

| 자료 | 처리 | chunk |
| --- | --- | ---: |
| 2024 내국인 조사개요·최종보고서 | PDF | 189 |
| 2024 외국인 조사개요·최종보고서 | PDF | 382 |
| 2025 내국인 보고서 | PDF | 388 |
| 2025 외국인 보고서·인포그래픽 | PDF | 405 |
| 2026 외국인 잠정치 보고서(4차/8월) | PDF, `status=preliminary` | 143 |
| 2024·2025 내/외국인 통계표 | 표 → 텍스트 | 3,253 |
| 2019~2025 외국인 통합 통계표 | 표 → 텍스트(통합 과정 범주 조정 주의 문구 포함) | 875 |
| 서울시 관광 명소 / 문화공간 / 문화행사 | 공공데이터 | 508 / 1,093 / 381 |
| 자치구 길관광·관광지·특화거리, 관광지 분석 CSV | 공공데이터 | 260 / 67 |
| **합계** | | **7,944** |

색인하지 않는 자료(설문지, 코드북·코드표, 응답자 원자료)는 `manifest.json`의 `index: false`와 `exclude_reason`에 이유를 남긴다. 원자료는 집계된 통계표로 대체하고, 설문지는 결과 수치가 없어 검색 노이즈만 늘리기 때문이다.

> `source_url`은 원본 게시 페이지 주소를 확인해 채운다. 출처를 확인하지 못한 항목(관광지 분석 CSV의 제공 기관)은 비워 두었다.

## 인덱스 빌드

원천 자료가 바뀌었을 때만 실행한다.

```bash
cd rag-server
pip install -r requirements.txt

python -m scripts.build_index                  # BM25 (외부 API 호출 없음, 약 1분)
python -m scripts.build_index --embed          # + Gemini 임베딩 (GEMINI_API_KEY 필요)
python -m scripts.build_index --only survey-2026-foreign-preliminary   # 특정 문서만 점검
python -m scripts.build_index --today 2026-11-01                       # 문화행사 만료 기준일 지정
```

빌드 결과 요약은 `index/meta.json`(문서별 chunk 수·글자 수, 빌드 시각, 원천 파일 지문)에 기록된다.

**문화행사는 시간이 지나면 만료된다.** 검색 시점에도 종료된 행사는 제외하지만, 새 행사를 반영하려면 `서울시 문화행사 정보.json`을 갱신한 뒤 다시 빌드한다(월 1회 권장).

## 자료 추가 방법

1. 파일을 성격에 맞는 폴더(`reports/`, `statistics/`, `places/`)에 넣는다.
2. `data/manifest.json`에 항목을 추가한다.

```json
{
  "id": "survey-2026-foreign-report",
  "path": "reports/2026_foreign/[보고서] 2026년 서울관광 실태조사_외국인.pdf",
  "loader": "pdf",
  "collection": "survey_report",
  "title": "2026 서울관광 실태조사(외국인) 보고서",
  "year": 2026,
  "audience": "foreign",
  "status": "confirmed",
  "publisher": "서울관광재단",
  "published_at": "YYYY-MM-DD",
  "source_url": ""
}
```

| 필드 | 값 |
| --- | --- |
| `loader` | `pdf`, `stats_xlsx`, `attractions_json`, `culture_spaces_json`, `culture_events_json`, `district_csv`, `analytics_csv` |
| `collection` | `survey_report`, `survey_stats`, `place`, `event`, `analytics` |
| `audience` | `domestic`, `foreign`, `all` |
| `status` | `confirmed`(확정치), `preliminary`(잠정치), `reference`(공공데이터) |
| `index` | `false`면 보관만 하고 색인하지 않는다(`exclude_reason` 필수) |

3. `python -m scripts.build_index`로 다시 빌드하고 `index/`를 커밋한다.
4. 2026 확정 보고서가 나오면 잠정치 항목을 `index: false`로 바꾸거나 함께 두되, `status`로 구분한다.

## 검색 API (remote 모드)

```bash
cd rag-server
RAG_API_KEY=change-me uvicorn main:app --port 8001
```

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/api/v1/rag/health` | 인덱스 상태(chunk 수, 컬렉션별 수, 빌드 시각), 캐시 통계 |
| `GET` | `/api/v1/rag/documents` | 원천 자료 목록·색인 여부·제외 사유 (`X-RAG-Key`) |
| `POST` | `/api/v1/rag/search` | 검색 (`X-RAG-Key`) |

```http
POST /api/v1/rag/search
X-RAG-Key: change-me
Content-Type: application/json

{ "query": "2026 외국인 관광객 체류일", "topK": 4, "collections": ["survey_report"], "maxCharsPerHit": 700 }
```

```json
{
  "query": "2026 외국인 관광객 체류일",
  "hints": { "years": [2026], "months": [], "audience": "foreign", "intents": ["survey"] },
  "hits": [
    {
      "id": "survey-2026-foreign-preliminary:00092",
      "docId": "survey-2026-foreign-preliminary",
      "collection": "survey_report",
      "title": "2026 서울관광 실태조사(외국인) 잠정치 보고서(4차/8월)",
      "year": 2026,
      "audienceLabel": "외국인",
      "status": "preliminary",
      "statusLabel": "잠정치",
      "location": "PDF p.54",
      "text": "2. 권역별 서울방문 관광객 특징\n□ 중국 [사례수 : (1차) 199명 / (2차) 219명 / (3차) 200명 / (4차) 204명] …",
      "score": 93.4471
    }
  ],
  "dense": false,
  "cached": false,
  "tookMs": 1.6
}
```

`RAG_API_KEY`가 비어 있으면 인증하지 않는다(로컬 개발용). 외부에 노출할 때는 반드시 설정한다.

## 검색 로직 요약

```text
질의 → 연도/월/대상/의도 추출 → 질의 확장(소비→지출 …)
     → BM25 점수 × 메타데이터 가중치
        · 연도 일치 ×1.5, 다른 연도 실태조사 ×0.5
        · 대상(외국인/내국인) 일치 ×1.25, 불일치 ×0.6
        · 연도 미지정: 최신 확정치 ×1.1, 잠정치 ×0.85
        · 조사개요 페이지 ×0.6 (방법론 질문 제외)
        · 종료된 문화행사 제외, 질문한 달과 겹치는 행사 ×1.6
     → (dense 인덱스가 있으면) 임베딩 코사인과 RRF 융합
     → 문서당 최대 2개, 다중 연도 질문은 연도별 균등 배분 → top-k
```

임베딩 dense 검색은 remote 모드에서만 질의 임베딩을 호출한다. embedded 모드는 BM25만 사용한다.
