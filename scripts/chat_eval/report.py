import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from app.core.config import BASE_DIR

RESULTS_DIR = BASE_DIR / "eval_results"

# (metric key, 표에 쓰는 약칭)
METRICS = (
    ("source_hit", "hit"),
    ("source_condition_rate", "src_cond"),
    ("answer_correctness", "correct"),
    ("faithfulness", "faithful"),
    ("answer_condition", "ans_cond"),
    ("no_unsupported_date", "no_date"),
    ("no_unsupported_price_hours", "no_p/h"),
    ("must_include", "include"),
    ("language_match", "lang"),
    ("used_ai", "used_ai"),
)
GROUPINGS = ("category", "prompt_style", "traveler_type", "persona", "language")


def collect_rows(results) -> list[dict]:
    rows = []
    for item in results:
        run, example = item["run"], item["example"]
        scores, comments = {}, {}
        for result in item["evaluation_results"]["results"]:
            scores[result.key] = result.score
            comments[result.key] = result.comment
        outputs = run.outputs or {}
        rows.append({
            **example.metadata,
            "message": example.inputs["message"],
            "answer": outputs.get("answer"),
            "sources": [source["title"] for source in outputs.get("sources", [])],
            "error": run.error,
            "scores": scores,
            "comments": comments,
        })
    return sorted(rows, key=lambda row: row["item_id"])


def mean(values) -> float | None:
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def summarize(rows: list[dict]) -> dict:
    summary = {}
    for key, _ in METRICS:
        scores = [row["scores"].get(key) for row in rows]
        applicable = [score for score in scores if score is not None]
        if applicable:
            summary[key] = {"mean": mean(applicable), "n": len(applicable)}
    return summary


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def _cell(value: float | None) -> str:
    return "  - " if value is None else f"{value * 100:3.0f}%"


def print_report(rows: list[dict], summary: dict, errors: int) -> None:
    print(f"\n=== 전체 ({len(rows)}문항) ===")
    for key, _ in METRICS:
        if key in summary:
            print(f"  {key:28s} {summary[key]['mean'] * 100:5.1f}%   (n={summary[key]['n']})")

    shown = [(key, short) for key, short in METRICS if key in summary]
    for grouping in GROUPINGS:
        groups = defaultdict(list)
        for row in rows:
            groups[row[grouping]].append(row)
        print(f"\n--- {grouping}별 ---")
        print(_pad("", 24) + " n  " + " ".join(f"{short:>8s}" for _, short in shown))
        for label, members in sorted(groups.items()):
            cells = [_cell(mean(row["scores"].get(key) for row in members)) for key, _ in shown]
            print(_pad(label, 24) + f"{len(members):2d}  " + " ".join(f"{cell:>8s}" for cell in cells))

    def failing(row: dict) -> list[str]:
        return [
            key for key, _ in METRICS
            if key != "used_ai" and row["scores"].get(key) is not None and row["scores"][key] < 1
        ]

    failed = [row for row in rows if failing(row)]
    print(f"\n=== 만점이 아닌 질문 {len(failed)}개 (상세는 저장된 JSON의 comments 참고) ===")
    for row in failed:
        print(f"  {row['item_id']} [{row['prompt_style']}/{row['persona']}/{row['category']}] {', '.join(failing(row))}")

    not_ai = [row["item_id"] for row in rows if row["scores"].get("used_ai") == 0]
    if not_ai:
        print(f"\n[주의] OpenAI 호출 실패로 fallback 답변이 된 질문 {len(not_ai)}개: {', '.join(not_ai)}")
        print("       이 질문들은 답변 품질 지표에서 제외됐습니다. 다시 실행하거나 rate limit을 확인하세요.")
    if errors:
        print(f"\n[주의] target 실행 중 오류가 난 질문 {errors}개가 있습니다. 위 로그를 확인하세요.")


def save(rows: list[dict], meta: dict, name: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{name}.json"
    payload = {"meta": meta, "summary": summarize(rows), "rows": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def _resolve(path_or_name: str) -> Path:
    path = Path(path_or_name)
    return path if path.exists() else RESULTS_DIR / f"{path_or_name}.json"


def compare(before_ref: str, after_ref: str) -> None:
    before = json.loads(_resolve(before_ref).read_text(encoding="utf-8"))
    after = json.loads(_resolve(after_ref).read_text(encoding="utf-8"))
    if before["meta"].get("split") != after["meta"].get("split"):
        print(f"[경고] split이 다릅니다: {before['meta'].get('split')} vs {after['meta'].get('split')} — 같은 평가셋끼리 비교해야 합니다.")

    before_rows = {row["item_id"]: row for row in before["rows"]}
    after_rows = {row["item_id"]: row for row in after["rows"]}
    shared = sorted(before_rows.keys() & after_rows.keys())
    print(f"before: {before['meta'].get('experiment')}  (git {before['meta'].get('git_sha')}, prompt {before['meta'].get('system_prompt_sha')})")
    print(f"after : {after['meta'].get('experiment')}  (git {after['meta'].get('git_sha')}, prompt {after['meta'].get('system_prompt_sha')})")
    print(f"공통 질문 {len(shared)}개 기준\n")

    print(f"{'metric':28s} {'before':>8s} {'after':>8s} {'delta':>8s}")
    regressions = defaultdict(list)
    for key, _ in METRICS:
        b = [before_rows[i]["scores"].get(key) for i in shared]
        a = [after_rows[i]["scores"].get(key) for i in shared]
        mb, ma = mean(b), mean(a)
        if mb is None or ma is None:
            continue
        print(f"{key:28s} {mb * 100:7.1f}% {ma * 100:7.1f}% {(ma - mb) * 100:+7.1f}p")
        for item_id, bs, as_ in zip(shared, b, a):
            if bs is not None and as_ is not None and as_ < bs:
                regressions[item_id].append(key)

    print(f"\n=== 오히려 나빠진 질문 {len(regressions)}개 (개선 과정에서 생긴 부작용 확인용) ===")
    for item_id, keys in sorted(regressions.items()):
        print(f"  {item_id} {after_rows[item_id]['message'][:40]!r}: {', '.join(keys)}")


METRIC_LABELS = {
    "source_hit": "검색 적중률",
    "source_condition_rate": "검색 조건 충족률",
    "answer_correctness": "답변 정확도",
    "faithfulness": "근거 충실도",
    "answer_condition": "답변 조건 충족률",
    "no_unsupported_date": "근거 없는 날짜 없음",
    "no_unsupported_price_hours": "근거 없는 가격·시각 없음",
    "must_include": "필수 정보 포함",
    "language_match": "요청 언어 일치",
    "used_ai": "AI 호출 성공",
}
MAIN_METRICS = (
    "source_hit", "source_condition_rate", "answer_correctness", "faithfulness",
    "answer_condition", "no_unsupported_date", "no_unsupported_price_hours", "must_include",
)


def load_result(ref: str) -> dict:
    return json.loads(_resolve(ref).read_text(encoding="utf-8"))


def group_scores(rows: list[dict], grouping: str, metric: str) -> dict[str, tuple[float | None, int]]:
    """grouping 값별 (평균, 적용 문항 수). grouping='overall'이면 전체 한 줄."""
    groups = defaultdict(list)
    for row in rows:
        groups["전체" if grouping == "overall" else row[grouping]].append(row["scores"].get(metric))
    return {
        label: (mean(values), sum(value is not None for value in values))
        for label, values in sorted(groups.items())
    }


def markdown_table(rows: list[dict], grouping: str, metrics: list[str]) -> str:
    """README에 붙일 마크다운 표. 셀은 '평균% (적용 문항 수)'. 적용 대상이 없으면 '-'."""
    if grouping == "overall":
        lines = ["| 지표 | 점수 | 적용 문항 |", "| --- | ---: | ---: |"]
        for metric in metrics:
            value, n = group_scores(rows, "overall", metric)["전체"]
            if value is not None:
                lines.append(f"| {METRIC_LABELS[metric]} (`{metric}`) | {value * 100:.1f}% | {n} |")
        return "\n".join(lines)

    labels = sorted({row[grouping] for row in rows})
    sizes = {label: sum(row[grouping] == label for row in rows) for label in labels}
    lines = [
        f"| {grouping} | 문항 | " + " | ".join(METRIC_LABELS[m] for m in metrics) + " |",
        "| --- | ---: | " + " | ".join("---:" for _ in metrics) + " |",
    ]
    for label in labels:
        cells = []
        for metric in metrics:
            value, n = group_scores(rows, grouping, metric)[label]
            cells.append("-" if value is None else f"{value * 100:.0f}% ({n})")
        lines.append(f"| {label} | {sizes[label]} | " + " | ".join(cells) + " |")
    return "\n".join(lines)
