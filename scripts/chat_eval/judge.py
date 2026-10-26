"""LLM-as-judge: 답변 정확도·근거 충실도·조건 충족을 0/1로 채점한다.

질문 한 건당 judge를 한 번만 호출해 세 지표를 함께 받는다.
챗봇과 같은 모델이 채점하면 자기 답변에 후해질 수 있으므로, 가능하면 --judge-model로 더 강한 다른 모델을 지정한다.
"""
import json
import time

import httpx

from app.core.config import get_settings

settings = get_settings()

JUDGE_PROMPT = """You are a strict evaluator of a Seoul travel chatbot.
The chatbot must answer ONLY from the retrieved context. It must not guess opening hours, prices, event dates, or any attribute that is not in the context.

[Question]
{question}

[Recent conversation history]
{history}

[Retrieved context - the only allowed evidence]
{context}

[Chatbot answer]
{answer}

[Evaluation criteria written by the dataset author - ground truth for correctness]
{criteria}

[Explicit conditions in the question (district / content type)]
{constraints}

Score each item as 0 or 1.
- correctness: 1 only if the answer satisfies the evaluation criteria. If the criteria say some information is unavailable, the answer must clearly say it is unavailable (or ask a clarifying question) and must NOT state the missing fact. Answers in the wrong language fail when the criteria require a specific language.
- faithfulness: 1 only if every concrete claim in the answer (place names, addresses, phone numbers, dates, hours, prices, and characteristics such as quiet/safe/photogenic) is supported by the retrieved context. Judge ONLY against the retrieved context, never with outside knowledge. Polite phrases and suggestions to refine the query are fine.
- condition_met: 1 only if every place the answer presents satisfies the explicit conditions. Use null when no conditions are listed.

Reply with JSON only: {{"correctness": 0 or 1, "faithfulness": 0 or 1, "condition_met": 0 or 1 or null, "reason": "<one or two sentences in Korean naming the specific failure, or 'ok'>"}}"""

SKIPPED_KEYS = ("answer_correctness", "faithfulness", "answer_condition")


def _post_with_retry(url: str, **kwargs) -> dict:
    for attempt in range(5):
        response = httpx.post(url, timeout=60.0, **kwargs)
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 4:
            time.sleep(4 * 2**attempt)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("unreachable")


def _call_openai(prompt: str, model: str) -> str:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    if not model.startswith(("gpt-5", "o1", "o3", "o4")):  # 추론 모델은 temperature 지정을 받지 않는다.
        body["temperature"] = 0
    payload = _post_with_retry(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json=body,
    )
    return payload["choices"][0]["message"]["content"]


def make_judge_evaluator(model: str):
    def llm_judge(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        if not outputs.get("used_ai"):
            skipped = "OpenAI 호출 실패(fallback 답변)라 채점에서 제외"
            return {"results": [{"key": key, "score": None, "comment": skipped} for key in SKIPPED_KEYS]}

        constraints = reference_outputs.get("constraints")
        history = inputs.get("history") or []
        prompt = JUDGE_PROMPT.format(
            question=inputs["message"],
            history="\n".join(f"{turn['role']}: {turn['content']}" for turn in history[-4:]) or "(none)",
            context=outputs["context"],
            answer=outputs["answer"],
            criteria=reference_outputs["criteria"],
            constraints=json.dumps(constraints, ensure_ascii=False) if constraints else "(none)",
        )
        try:
            verdict = json.loads(_call_openai(prompt, model))
        except Exception as error:  # judge 실패가 평가 전체를 멈추지 않게 하되, 결과에는 실패 사유를 남긴다.
            failed = f"judge 호출/파싱 실패: {type(error).__name__}: {error}"
            return {"results": [{"key": key, "score": None, "comment": failed} for key in SKIPPED_KEYS]}

        reason = str(verdict.get("reason", ""))
        results = [
            {"key": "answer_correctness", "score": _binary(verdict.get("correctness")), "comment": reason},
            {"key": "faithfulness", "score": _binary(verdict.get("faithfulness")), "comment": reason},
        ]
        if constraints:
            results.append({"key": "answer_condition", "score": _binary(verdict.get("condition_met")), "comment": reason})
        else:
            results.append({"key": "answer_condition", "score": None, "comment": "조건 없음"})
        return {"results": results}

    return llm_judge


def _binary(value) -> int | None:
    return int(value) if value in (0, 1) else None
