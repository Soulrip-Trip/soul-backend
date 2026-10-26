import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.config import BASE_DIR
from app.db.database import SessionLocal
from app.db.models import FestivalSchedule, Location, Post

DATASET_PATH = BASE_DIR / "data" / "eval" / "chat_eval_set.json"
DATASET_NAME = "soulrip-chatbot-eval"
SPLITS = ("dev", "holdout")
LANGUAGES = {"ko", "en", "ja", "zh", "fr", "es", "de"}

# 질문 id(Q01 ...)에서 LangSmith Example id를 고정 생성하기 위한 namespace. 바꾸면 sync가 새 예제를 만든다.
_EXAMPLE_NAMESPACE = uuid.UUID("5f0c1d58-6a52-4a39-9b43-2d5c8e0f7a11")


def load_dataset() -> tuple[dict, list[dict]]:
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return payload["meta"], payload["items"]


def example_id(item_id: str) -> uuid.UUID:
    return uuid.uuid5(_EXAMPLE_NAMESPACE, item_id)


def item_metadata(item: dict) -> dict:
    return {
        "item_id": item["id"],
        "split": item["split"],
        "persona": item["persona"],
        "prompt_style": item["prompt_style"],
        "category": item["category"],
        "traveler_type": "solo" if item["persona"].startswith("solo_") else "non_solo",
        "language": item["inputs"]["language"],
    }


def as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def validate(meta: dict, items: list[dict]) -> tuple[list[str], list[str]]:
    """평가셋 형식과 DB 사실을 검증한다. (errors, warnings)를 돌려준다."""
    errors: list[str] = []
    warnings: list[str] = []

    seen: set[str] = set()
    for item in items:
        qid = item.get("id", "?")
        if qid in seen:
            errors.append(f"{qid}: id 중복")
        seen.add(qid)
        if item["split"] not in SPLITS:
            errors.append(f"{qid}: split은 {SPLITS} 중 하나여야 함 ({item['split']})")
        if item["persona"] not in meta["personas"]:
            errors.append(f"{qid}: 정의되지 않은 persona ({item['persona']})")
        if item["prompt_style"] not in meta["prompt_styles"]:
            errors.append(f"{qid}: 정의되지 않은 prompt_style ({item['prompt_style']})")
        inputs = item["inputs"]
        if not 1 <= len(inputs["message"]) <= 2000:
            errors.append(f"{qid}: message 길이는 1~2000자여야 함 (ChatRequest 제약)")
        if inputs["language"] not in LANGUAGES:
            errors.append(f"{qid}: 지원하지 않는 language ({inputs['language']})")
        for turn in inputs["history"]:
            if turn.get("role") not in ("user", "assistant") or not turn.get("content"):
                errors.append(f"{qid}: history 항목 형식 오류 ({turn})")
        if not item["expected"].get("criteria"):
            errors.append(f"{qid}: expected.criteria 누락")

    with SessionLocal() as db:
        known_content_ids = set(db.scalars(select(Location.content_id)))
        known_post_ids = {str(pid) for pid in db.scalars(select(Post.id))}
        combos = {
            (district, content_type)
            for district, content_type in db.execute(
                select(Location.district, Location.content_type).distinct()
            )
        }
        stats = {
            "locations": db.scalar(select(func.count(Location.id))),
            "festival_schedules": db.scalar(select(func.count(FestivalSchedule.id))),
            "posts": db.scalar(select(func.count(Post.id))),
        }

    for item in items:
        qid, expected = item["id"], item["expected"]
        for key in ("expected_content_ids", "expected_any_content_ids"):
            for content_id in expected.get(key, []):
                if content_id not in known_content_ids:
                    errors.append(f"{qid}: {key}의 content_id {content_id}가 DB에 없음")
        for post_id in expected.get("expected_post_ids", []):
            if post_id not in known_post_ids:
                errors.append(f"{qid}: expected_post_ids의 {post_id}가 DB에 없음")
        constraints = expected.get("constraints", {})
        if constraints:
            districts = as_list(constraints["district"]) if "district" in constraints else None
            types = as_list(constraints["content_type"]) if "content_type" in constraints else None
            satisfiable = any(
                (districts is None or district in districts) and (types is None or content_type in types)
                for district, content_type in combos
            )
            if not satisfiable:
                errors.append(f"{qid}: constraints {constraints}를 만족하는 장소가 DB에 없음")

    for key, expected_count in meta.get("db_snapshot", {}).items():
        if stats.get(key) != expected_count:
            warnings.append(
                f"DB 스냅샷 불일치: {key} 평가셋 작성 시 {expected_count}개 → 현재 {stats.get(key)}개. "
                "정답이 어긋났을 수 있으니 check 결과를 확인하세요."
            )
    return errors, warnings


def to_local_examples(items: list[dict]):
    from langsmith import schemas

    dataset_id = uuid.uuid5(_EXAMPLE_NAMESPACE, DATASET_NAME)
    now = datetime.now(timezone.utc)
    return [
        schemas.Example(
            id=example_id(item["id"]),
            dataset_id=dataset_id,
            created_at=now,
            inputs=item["inputs"],
            outputs=item["expected"],
            metadata=item_metadata(item),
        )
        for item in items
    ]


def sync_to_langsmith(client, items: list[dict]) -> dict:
    """평가셋을 LangSmith Dataset에 반영한다. 같은 id의 예제는 update, 새 예제는 create 한다."""
    if not client.has_dataset(dataset_name=DATASET_NAME):
        meta, _ = load_dataset()
        client.create_dataset(DATASET_NAME, description=meta["description"])

    existing = {str(example.id) for example in client.list_examples(dataset_name=DATASET_NAME)}
    creates, updates = [], []
    for item in items:
        eid = example_id(item["id"])
        common = {
            "id": eid,
            "inputs": item["inputs"],
            "metadata": item_metadata(item),
            "split": item["split"],
        }
        if str(eid) in existing:
            updates.append({**common, "outputs": item["expected"]})
        else:
            creates.append({**common, "reference_outputs": item["expected"]})

    if creates:
        client.create_examples(dataset_name=DATASET_NAME, examples=creates)
    if updates:
        client.update_examples(dataset_name=DATASET_NAME, updates=updates)

    stale = existing - {str(example_id(item["id"])) for item in items}
    return {"created": len(creates), "updated": len(updates), "stale_in_langsmith": len(stale)}
