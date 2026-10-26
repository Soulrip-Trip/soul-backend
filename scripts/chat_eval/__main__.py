"""Soulrip 챗봇 RAG 평가 CLI.

    python -m scripts.chat_eval check                        # 평가셋 형식·DB 정답 검증
    python -m scripts.chat_eval sync                         # 평가셋을 LangSmith Dataset에 반영
    python -m scripts.chat_eval run --tag baseline           # dev 평가를 돌려 LangSmith에 기록
    python -m scripts.chat_eval run --local --retrieval-only # 키 없이 검색 지표만 로컬에서 측정
    python -m scripts.chat_eval compare <before> <after>     # 저장된 두 결과를 비교
    python -m scripts.chat_eval chart <결과> --out x.svg      # 막대그래프(SVG). 결과 2개면 전후 비교
    python -m scripts.chat_eval table <결과> --by category    # README용 마크다운 표
"""
import argparse
import hashlib
import os
import subprocess
import sys
from datetime import datetime

from dotenv import load_dotenv

from app.core.config import BASE_DIR

load_dotenv(BASE_DIR / ".env")  # LangSmith SDK는 os.environ을 직접 읽으므로 .env를 환경변수로 올려 둔다.


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _select_items(items: list[dict], args) -> list[dict]:
    if args.split != "all":
        items = [item for item in items if item["split"] == args.split]
    if args.ids:
        wanted = {value.strip() for value in args.ids.split(",")}
        items = [item for item in items if item["id"] in wanted]
    return items[: args.limit] if args.limit else items


def cmd_check(args) -> int:
    from scripts.chat_eval import dataset

    meta, items = dataset.load_dataset()
    errors, warnings = dataset.validate(meta, items)
    for warning in warnings:
        print(f"[경고] {warning}")
    for error in errors:
        print(f"[오류] {error}")
    if errors:
        return 1

    from collections import Counter

    print(f"평가셋 검증 통과: {len(items)}문항")
    for field in ("split", "prompt_style", "category", "language"):
        counts = Counter(item[field] if field in item else item["inputs"][field] for item in items)
        print(f"  {field:13s} {dict(counts)}")
    solo = sum(item["persona"].startswith("solo_") for item in items)
    print(f"  traveler_type {{'solo': {solo}, 'non_solo': {len(items) - solo}}}")
    return 0


def cmd_sync(args) -> int:
    from langsmith import Client

    from scripts.chat_eval import dataset

    if not os.getenv("LANGSMITH_API_KEY"):
        print("LANGSMITH_API_KEY가 없습니다. .env에 추가한 뒤 다시 실행하세요.")
        return 1
    meta, items = dataset.load_dataset()
    errors, _ = dataset.validate(meta, items)
    if errors:
        print("평가셋 검증에 실패해 sync를 중단합니다. 먼저 `python -m scripts.chat_eval check`를 확인하세요.")
        return 1

    result = dataset.sync_to_langsmith(Client(), items)
    print(f"Dataset '{dataset.DATASET_NAME}' 반영 완료: {result}")
    if result["stale_in_langsmith"]:
        print("  (LangSmith에는 있지만 평가셋 파일에는 없는 예제가 있습니다. 필요하면 웹에서 직접 삭제하세요.)")
    return 0


def cmd_run(args) -> int:
    local = args.local
    # evaluate가 만드는 trace 외에 불필요한 업로드가 생기지 않도록, 로컬 실행에서는 tracing을 끈다.
    os.environ["LANGSMITH_TRACING"] = "false" if local else "true"

    from langsmith import Client, evaluate

    from app.core.config import get_settings
    from app.services import chat_service
    from scripts.chat_eval import dataset, evaluators, judge, report
    from scripts.chat_eval.target import make_target

    settings = get_settings()
    meta, items = dataset.load_dataset()
    errors, warnings = dataset.validate(meta, items)
    for warning in warnings:
        print(f"[경고] {warning}")
    if errors:
        print("평가셋 검증에 실패했습니다. `python -m scripts.chat_eval check`를 확인하세요.")
        return 1

    items = _select_items(items, args)
    if args.retrieval_only and not settings.openai_api_key:
        skipped = [item["id"] for item in items if item["inputs"]["language"] != "ko"]
        if skipped:
            print(f"[안내] OPENAI_API_KEY가 없어 한국어 검색어 변환을 할 수 없으므로 외국어 질문 {len(skipped)}개는 제외합니다.")
            items = [item for item in items if item["inputs"]["language"] == "ko"]
    if not items:
        print("평가할 질문이 없습니다. --split/--ids/--limit을 확인하세요.")
        return 1

    use_judge = not args.retrieval_only and not args.no_judge
    if not args.retrieval_only and not settings.openai_api_key:
        print("OPENAI_API_KEY가 없으면 챗봇은 fallback 답변만 반환해 답변 평가가 무의미합니다. 검색 지표만 보려면 --retrieval-only를 쓰세요.")
        return 1
    if not local and not os.getenv("LANGSMITH_API_KEY"):
        print("LANGSMITH_API_KEY가 없습니다. .env에 추가하거나, 업로드 없이 보려면 --local을 쓰세요.")
        return 1

    evaluator_list = list(evaluators.RETRIEVAL_EVALUATORS)
    judge_label = None
    if not args.retrieval_only:
        evaluator_list += list(evaluators.ANSWER_EVALUATORS)
    if use_judge:
        judge_model = args.judge_model or settings.openai_model
        judge_label = f"openai:{judge_model}"
        evaluator_list.append(judge.make_judge_evaluator(judge_model))

    mode = "retrieval" if args.retrieval_only else "full"
    split_label = args.split if not args.ids and not args.limit else f"{args.split}-subset"
    prefix = f"{args.tag}-{split_label}-{mode}"
    metadata = {
        "tag": args.tag,
        "split": split_label,
        "mode": mode,
        "git_sha": _git("rev-parse", "--short", "HEAD"),
        "app_dirty": bool(_git("status", "--porcelain", "--", "app")),
        "system_prompt_sha": hashlib.sha1(chat_service._system_instruction("ko").encode("utf-8")).hexdigest()[:8],
        "chat_model": settings.openai_model,
        "judge": judge_label,
        "questions": len(items),
    }

    if local:
        data = dataset.to_local_examples(items)
    else:
        client = Client()
        if not client.has_dataset(dataset_name=dataset.DATASET_NAME):
            print(f"LangSmith에 Dataset '{dataset.DATASET_NAME}'이 없습니다. 먼저 `python -m scripts.chat_eval sync`를 실행하세요.")
            return 1
        wanted = {item["id"] for item in items}
        splits = None if args.split == "all" else [args.split]
        data = [
            example
            for example in client.list_examples(dataset_name=dataset.DATASET_NAME, splits=splits)
            if example.metadata["item_id"] in wanted
        ]
        if len(data) != len(items):
            print(f"LangSmith Dataset({len(data)}개)과 로컬 평가셋({len(items)}개)이 다릅니다. `sync`를 다시 실행하세요.")
            return 1

    print(f"실행: {prefix} / {len(items)}문항 / local={local} / judge={judge_label}")
    results = evaluate(
        make_target(args.retrieval_only),
        data=data,
        evaluators=evaluator_list,
        experiment_prefix=prefix,
        description=f"Soulrip chatbot eval ({mode}) tag={args.tag}",
        metadata=metadata,
        max_concurrency=args.max_concurrency,
        upload_results=not local,
    )

    rows = report.collect_rows(results)
    summary = report.summarize(rows)
    experiment = f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}" if local else results.experiment_name
    metadata["experiment"] = experiment
    path = report.save(rows, metadata, experiment)
    report.print_report(rows, summary, errors=sum(1 for row in rows if row["error"]))
    print(f"\n결과 저장: {path}")
    return 0


def _metric_list(value: str | None) -> list[str] | None:
    return [item.strip() for item in value.split(",")] if value else None


def cmd_chart(args) -> int:
    from pathlib import Path

    from scripts.chat_eval import chart, report

    results = [report.load_result(ref) for ref in args.results]
    path = chart.build_chart(results, args.by, _metric_list(args.metrics), args.title, Path(args.out))
    print(f"차트 저장: {path}")
    return 0


def cmd_table(args) -> int:
    from scripts.chat_eval import report

    result = report.load_result(args.result)
    default = report.MAIN_METRICS if args.by == "overall" else (
        "source_condition_rate", "answer_correctness", "faithfulness", "answer_condition"
    )
    print(report.markdown_table(result["rows"], args.by, _metric_list(args.metrics) or list(default)))
    return 0


def cmd_compare(args) -> int:
    from scripts.chat_eval import report

    report.compare(args.before, args.after)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.chat_eval", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="평가셋 형식과 DB 정답을 검증한다.").set_defaults(func=cmd_check)
    sub.add_parser("sync", help="평가셋을 LangSmith Dataset에 반영한다.").set_defaults(func=cmd_sync)

    run = sub.add_parser("run", help="챗봇을 평가한다.")
    run.add_argument("--tag", default="run", help="실험 이름 접두어. 예: baseline, prompt-v2")
    run.add_argument("--split", choices=("dev", "holdout", "all"), default="dev", help="기본은 dev. holdout은 개선을 마친 뒤 최종 검증에서만 쓴다.")
    run.add_argument("--local", action="store_true", help="LangSmith에 업로드하지 않고 로컬에서만 실행한다. (LANGSMITH_API_KEY 불필요)")
    run.add_argument("--retrieval-only", action="store_true", help="LLM 호출 없이 검색 지표(source_hit, source_condition_rate)만 측정한다.")
    run.add_argument("--no-judge", action="store_true", help="LLM-as-judge 채점을 건너뛴다.")
    run.add_argument("--judge-model", default=None, help="채점 모델. 기본은 챗봇과 같은 OPENAI_MODEL. 자기 편향을 줄이려면 더 강한 다른 모델을 지정한다.")
    run.add_argument("--max-concurrency", type=int, default=2, help="동시 실행 수. OpenAI rate limit(429)이 나면 1로 낮춘다.")
    run.add_argument("--ids", default=None, help="쉼표로 구분한 질문 id만 실행. 예: Q01,Q02")
    run.add_argument("--limit", type=int, default=None, help="앞에서 N개만 실행 (스모크 테스트용)")
    run.set_defaults(func=cmd_run)

    compare = sub.add_parser("compare", help="저장된 두 실행 결과를 비교한다.")
    compare.add_argument("before")
    compare.add_argument("after")
    compare.set_defaults(func=cmd_compare)

    by_choices = ("overall", "category", "prompt_style", "traveler_type", "persona", "language")

    chart = sub.add_parser("chart", help="결과를 막대그래프(SVG)로 그린다. 결과 2개를 주면 전후 비교 차트가 된다.")
    chart.add_argument("results", nargs="+", help="eval_results의 결과 이름 또는 JSON 경로 (1개, 또는 before after 2개)")
    chart.add_argument("--by", choices=by_choices, default="overall")
    chart.add_argument("--metrics", default=None, help="쉼표 구분 지표. 전후 비교의 그룹별 차트는 첫 번째만 사용한다.")
    chart.add_argument("--title", default=None)
    chart.add_argument("--out", required=True, help="저장할 .svg 경로")
    chart.set_defaults(func=cmd_chart)

    table = sub.add_parser("table", help="결과를 README용 마크다운 표로 출력한다.")
    table.add_argument("result")
    table.add_argument("--by", choices=by_choices, default="overall")
    table.add_argument("--metrics", default=None)
    table.set_defaults(func=cmd_table)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
