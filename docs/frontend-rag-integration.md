# Frontend Integration Guide — RAG 챗봇 · 백엔드 개선 반영

> 대상: `soulrip-frontend` 개발자와 프론트엔드 AI 하네스
> 기준 백엔드: `POST /api/v1/chat` (RAG 적용), `POST /api/v1/ai-insights/today` (오류 코드 정리)

## 0. 한 줄 요약

**RAG는 서버 내부에서만 동작한다.** 프론트엔드는 지금처럼 `POST /chat`만 호출하면 되고, RAG 서버 주소·키·데이터를 알 필요가 없다. 프론트에서 할 일은 **응답 타입을 실제 응답(camelCase)에 맞추고, 새 출처 유형을 표시하고, history를 올바르게 보내는 것**이다.

| 해야 할 것 | 하면 안 되는 것 |
| --- | --- |
| `ChatSource`·`ChatResponse` 타입을 camelCase로 수정 | 프론트에서 RAG 서버(`/api/v1/rag/*`) 직접 호출 |
| 출처 `type`별 링크·배지 표시(REPORT, EVENT 등) | 프론트 코드·`.env`에 Gemini/OpenAI/RAG 키 보관 |
| history에서 현재 질문·인사말·오류 메시지 제외 | 실태조사 PDF·통계를 프론트에서 불러와 프롬프트 조립 |
| 챗봇 요청 타임아웃·오류 상태 처리 | 프론트에서 답변 내용을 재가공해 수치 생성 |

---

## 1. API 계약

### Request (변경 없음)

```ts
POST /api/v1/chat
{
  "message": "2025년 외국인 관광객 특징 알려줘",   // 1~2000자
  "history": [{ "role": "user" | "assistant", "content": "..." }],
  "language": "ko" | "en" | "ja" | "zh" | "fr" | "es" | "de"
}
```

### Response — 필드는 **camelCase**

백엔드 응답 모델은 camelCase alias로 직렬화된다. 현재 프론트 타입의 `image_url`, `used_ai`는 실제 응답에 존재하지 않아 **항상 `undefined`** 이다(출처 썸네일이 표시되지 않는 원인).

아래 `sources`는 개발 DB에서 받은 실제 응답 일부다(`answer`는 형태만 표시).

```json
{
  "answer": "(Gemini 답변 또는 검색 결과 기반 기본 답변)",
  "sources": [
    {
      "type": "LOCATION", "id": "126938", "title": "양화진외국인선교사묘원(외인묘지)",
      "subtitle": "관광지 · 서울특별시 마포구 양화진길 46",
      "imageUrl": "https://tong.visitkorea.or.kr/cms/resource/36/3384436_image2_1.JPG", "url": ""
    },
    {
      "type": "REPORT", "id": "survey-2025-foreign-report:00110", "title": "2025 서울관광 실태조사(외국인) 보고서",
      "subtitle": "2025년 · 외국인 · 확정치 · PDF p.64", "imageUrl": "", "url": ""
    },
    {
      "type": "EVENT", "id": "seoul-culture-events:00159", "title": "TASTE OF GREEN(테이스트 오브 그린) 展",
      "subtitle": "2026-10-09 ~ 2026-11-08 · 용산구",
      "imageUrl": "https://culture.seoul.go.kr/cmmn/file/getImage.do?atchFileId=180d3c8c592144d19aabadb5acf794f3&thumb=Y",
      "url": "https://culture.seoul.go.kr/culture/culture/cultureEvent/view.do?cultcode=159543&menuNo=200009"
    }
  ],
  "suggestions": ["혼자 걷기 좋은 곳", "이번 달 축제", "종로구 문화시설"],
  "usedAi": false
}
```

### 출처 유형(`source.type`)

| type | 출처 | `id` | 권장 동작 |
| --- | --- | --- | --- |
| `LOCATION` | Soulrip DB 장소(축제·코스 포함) | `contentId` | `paths.placeDetail(id)` 내부 링크 |
| `FESTIVAL` | Soulrip DB 축제 일정 | `contentId` | `paths.festivalDetail(id)` 내부 링크 |
| `POST` | 커뮤니티 게시글 | 게시글 id | `paths.postDetail(id)` 내부 링크 |
| `REPORT` | **서울관광 실태조사**(보고서·통계표) | chunk id | 링크 없음. "조사 근거" 배지 + subtitle(연도·대상·확정/잠정·쪽) 표시 |
| `EVENT` | 서울시 문화행사(RAG) | chunk id | `url`이 있으면 외부 링크(새 탭) |
| `PLACE_INFO` | 서울시 관광 명소·문화공간·자치구 길(RAG) | chunk id | `url`이 있으면 외부 링크(새 탭) |
| `DATA` | 관광지 방문 데이터(RAG) | chunk id | 링크 없음 |

- `REPORT`의 `subtitle`에 **`잠정치`** 가 포함되면 2026 잠정 수치다. "잠정" 배지를 붙여 확정치와 구분한다.
- RAG 출처의 `id`는 내부 식별자이므로 화면에 노출하거나 라우팅에 쓰지 않는다.
- `suggestions`는 이제 **요청 언어로 번역되어** 온다.

---

## 2. 수정할 코드

### 2-1. `packages/api/src/domains/chat/chat.types.ts`

```ts
import type { Lang } from '@soulrip/config'

export interface ChatHistoryItem {
  role: 'user' | 'assistant'
  content: string
}

export type ChatSourceType =
  | 'LOCATION'
  | 'FESTIVAL'
  | 'POST'
  | 'REPORT'
  | 'EVENT'
  | 'PLACE_INFO'
  | 'DATA'

export interface ChatSource {
  type: ChatSourceType | (string & {}) // 서버에 새 유형이 추가돼도 타입 오류로 깨지지 않게
  id: string
  title: string
  subtitle: string
  imageUrl: string // ← image_url 아님
  url: string      // RAG 출처의 외부 상세 페이지. DB 출처는 ''
}

export interface ChatRequest {
  message: string
  history: ChatHistoryItem[]
  language: Lang
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
  suggestions: string[]
  usedAi: boolean // ← used_ai 아님
}
```

### 2-2. `src/widgets/chatbot/ui/ChatbotWidget.vue` — 출처 링크·이미지·배지

현재 `sourceLink()`는 `'place'`, `'festival'`(소문자)을 비교하지만 서버는 `'LOCATION'`, `'FESTIVAL'`(대문자)을 보내므로 **출처 링크가 동작하지 않는다.**

```ts
/** 내부 라우트로 이동할 수 있는 출처 */
function sourceLink(source: ChatSource): string | null {
  switch (source.type) {
    case 'LOCATION':
      return paths.placeDetail(source.id)
    case 'FESTIVAL':
      return paths.festivalDetail(source.id)
    case 'POST':
      return paths.postDetail(source.id)
    default:
      return null
  }
}

/** RAG 출처 중 외부 상세 페이지가 있는 경우 */
function externalLink(source: ChatSource): string | null {
  return !sourceLink(source) && source.url ? source.url : null
}

const isReport = (source: ChatSource) => source.type === 'REPORT'
const isPreliminary = (source: ChatSource) => isReport(source) && source.subtitle.includes('잠정치')
```

```vue
<li v-for="source in message.sources" :key="`${source.type}-${source.id}`">
  <component
    :is="sourceLink(source) ? RouterLink : externalLink(source) ? 'a' : 'div'"
    :to="sourceLink(source) ?? undefined"
    :href="externalLink(source) ?? undefined"
    :target="externalLink(source) ? '_blank' : undefined"
    :rel="externalLink(source) ? 'noopener noreferrer' : undefined"
    class="chatbot__source"
    :class="{ 'is-report': isReport(source) }"
    @click="sourceLink(source) && isMobile && closeChatbot()"
  >
    <img v-if="source.imageUrl" :src="source.imageUrl" alt="" loading="lazy" />
    <span>
      <strong class="ds-ellipsis">
        <em v-if="isReport(source)" class="chatbot__badge">{{ t.chat.reportBadge }}</em>
        <em v-if="isPreliminary(source)" class="chatbot__badge is-warn">{{ t.chat.preliminaryBadge }}</em>
        {{ source.title }}
      </strong>
      <small v-if="source.subtitle" class="ds-ellipsis">{{ source.subtitle }}</small>
    </span>
  </component>
</li>
```

7개 언어 locale(`src/shared/i18n/locales/*.ts`)의 `chat`에 배지 문구를 추가한다.

```ts
// ko
reportBadge: '조사 근거',
preliminaryBadge: '잠정',
// en
reportBadge: 'Survey',
preliminaryBadge: 'Preliminary',
```

### 2-3. `src/widgets/chatbot/model/useChatbot.ts` — history 구성

현재는 사용자 메시지를 `messages`에 **추가한 뒤** 최근 기록을 잘라 보내기 때문에, history 끝에 방금 보낸 질문이 그대로 들어간다. 백엔드가 `message`를 따로 붙이므로 같은 질문이 두 번 전달된다. 인사말·오류 메시지도 의미 없는 토큰이다.

> 백엔드가 이미 이 세 가지를 걸러내므로 지금 상태로도 동작은 한다. 다만 프론트에서 보내지 않으면 요청 크기가 줄고, 서버 응답 캐시 키가 안정된다.

```ts
async function send(text = input.value) {
  const message = text.trim()
  if (!message || loading.value) return

  // ① 현재 질문을 추가하기 "전"의 대화로 history를 만든다.
  // ② 인사말(greeting)·오류(error) 메시지는 제외한다.
  const history: ChatHistoryItem[] = messages.value
    .filter((item) => !item.kind)
    .slice(-CHAT_HISTORY_LIMIT)
    .map((item) => ({ role: item.role, content: item.content }))

  messages.value.push({ id: nextId++, role: 'user', content: message })
  input.value = ''
  loading.value = true

  try {
    const result = await chatApi.sendMessage({ message, history, language: lang.value })
    messages.value.push({
      id: nextId++,
      role: 'assistant',
      content: result.answer,
      sources: result.sources ?? [],
    })
    suggestions.value = result.suggestions ?? []
    completeJourneyStep('ask')
  } catch {
    messages.value.push({ id: nextId++, role: 'assistant', content: '', kind: 'error' })
  } finally {
    loading.value = false
  }
}
```

`CHAT_HISTORY_LIMIT`(현재 8)는 그대로 두면 된다. 서버는 최근 10개, 메시지당 800자까지만 사용한다.

### 2-4. 챗봇 요청 타임아웃

공용 `http` 클라이언트(`packages/api/src/core/http.ts`)에는 타임아웃이 없어, 외부 AI가 응답하지 않으면 로딩이 끝나지 않을 수 있다. 서버의 Gemini 타임아웃은 30초다. 챗봇 요청에만 35초 정도의 타임아웃을 두는 것을 권장한다.

```ts
// packages/api/src/domains/chat/chat.api.ts
export const chatApi = {
  sendMessage(request: ChatRequest, timeoutMs = 35_000) {
    return http.request<ChatResponse>('/chat', {
      method: 'POST',
      json: request,
      signal: AbortSignal.timeout(timeoutMs),
    })
  },
}
```

`AbortSignal.timeout`이 만료되면 `fetch`가 `TimeoutError`(DOMException)를 던지고, 공용 `http` 클라이언트는 이를 네트워크 오류(`ApiError`, status 0)로 바꿔 던진다. 현재 `useChatbot`의 `catch`가 모든 예외를 오류 메시지로 처리하므로 추가 분기는 필요 없다.

### 2-5. (선택) AI 사용 여부 표시

`usedAi === false`이면 Gemini 키가 없거나 호출이 실패해 **검색 결과만으로 만든 기본 답변**이다. 필요하면 답변 아래에 작은 안내 문구("검색 결과 기반 답변")를 표시한다.

---

## 3. AI Insight 오류 코드 변경

`POST /api/v1/ai-insights/today`의 성공 응답(`today/time/place/tip`, 각 `image_url`은 snake_case 유지)은 그대로다. 오류 상태코드만 원인별로 정리되었다.

| 상황 | 이전 | 현재 | `detail` |
| --- | --- | --- | --- |
| 서버에 `OPENAI_API_KEY` 없음 | 서버 기동 실패 | **503** | `OPENAI_API_KEY가 설정되지 않았습니다.` |
| 이미지가 있는 관광 데이터 없음 | 400 | **503** | `이미지가 포함된 관광 데이터가 없습니다.` |
| OpenAI 응답 형식·이미지 URL 규칙 위반 | 400 | **502** | `OpenAI 응답이 올바르지 않습니다: …` |
| OpenAI 연결 실패·타임아웃 | 500 | **503** | `OpenAI 서버에 연결할 수 없습니다.` |
| OpenAI 요청 한도 초과 | 500 | **429** | `OpenAI API 요청 한도를 초과했습니다. …` |

- `ApiError.status`가 503·502·429이면 **사용자 잘못이 아니므로** "잠시 후 다시 시도" 안내와 함께 기본(목업) 인사이트 카드로 대체하는 것을 권장한다.
- 같은 날 인사이트는 서버에서 10분간 캐시된다. 새로고침마다 다른 결과를 기대하는 UI(예: "다시 생성" 버튼)는 같은 결과가 나올 수 있음을 고려한다.

---

## 4. 그 밖의 변경 사항(프론트 작업 불필요)

| 변경 | 영향 |
| --- | --- |
| `GET /health` 응답에 `rag` 필드 추가 | 관리·디버깅용. 기존 필드 유지 |
| 큰 응답(1KB 이상) gzip 압축 | 브라우저가 자동으로 풀기 때문에 코드 변경 없음. 지도 2,000건 응답 약 82% 감소 |
| `X-Process-Time` 응답 헤더(서버 처리 ms) | CORS `expose_headers`에 포함되어 개발자 도구·코드에서 읽을 수 있음 |
| 목록 API N+1 제거, 주변 장소 검색 최적화 | 응답 필드·정렬 동일, 속도만 개선 |
| 챗봇 축제 일정 근거 | 원본 수정일을 축제일로 쓰지 않음. 일정이 없으면 AI가 날짜를 말하지 않음 |

---

## 5. 프론트엔드 AI 하네스에 전달할 체크리스트

```text
[ ] chat.types.ts: ChatSource.image_url → imageUrl, ChatResponse.used_ai → usedAi, ChatSource.url 추가, ChatSourceType 유니온 추가
[ ] ChatbotWidget.vue: source.image_url → source.imageUrl
[ ] ChatbotWidget.vue: sourceLink()를 LOCATION/FESTIVAL/POST 대문자 type으로 매핑, RAG 출처는 url이 있으면 외부 링크(_blank, noopener)
[ ] ChatbotWidget.vue: REPORT 배지, subtitle에 '잠정치'가 있으면 잠정 배지
[ ] i18n 7개 언어: chat.reportBadge, chat.preliminaryBadge 추가
[ ] useChatbot.ts: 현재 질문 push 전에 history 생성, kind(greeting/error) 메시지 제외
[ ] chat.api.ts: AbortSignal.timeout(35초)
[ ] AI Insight: 503/502/429 오류 시 재시도 안내 + 기본 카드 대체
[ ] RAG 서버 직접 호출·API 키 보관 코드가 없는지 확인
```

검증 순서

1. 백엔드 실행 → `GET /api/v1/health`의 `rag`가 `embedded:ready(…)`인지 확인
2. 챗봇에 "2025년 외국인 관광객 특징 알려줘" → `REPORT` 출처와 "조사 근거" 배지 확인
3. "2026년 외국인 관광객 체류일" → 잠정 배지와 답변의 "잠정치" 문구 확인
4. "이번 달 전시 추천" → `EVENT` 출처의 외부 링크가 새 탭으로 열리는지 확인
5. 장소 출처 클릭 → 장소 상세로 이동하는지, 썸네일이 보이는지 확인
6. 언어를 English로 바꿔 질문 → suggestions가 영어로 오는지 확인
