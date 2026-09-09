# AI Insights Domain Guide

AI Insight는 OpenAI를 사용하여 오늘의 혼행 인사이트를 구조화된 형태로 생성한다.

## Input

DB에서 이미지가 있는 장소와 현재/예정 축제 후보를 수집한다.

## Output

```text
today
time
place
tip
```

각 항목은 label, headline, description, image_url을 가진다.

## Invariants

- 입력 데이터만 사용한다.
- 모델 출력은 지정 JSON Schema를 따라야 한다.
- `image_url`은 입력 데이터의 URL만 허용한다.
- 없는 운영시간, 날씨, 혼잡도 등을 추측하지 않는다.
- OpenAI 응답이 비어 있거나 JSON으로 변환되지 않으면 명시적인 오류로 처리한다.
