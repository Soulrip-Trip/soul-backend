"""RAG 인덱스 빌드(오프라인 1회).

사용법 (rag-server 디렉터리에서)
    python -m scripts.build_index              # BM25 인덱스만 (외부 API 호출 없음)
    python -m scripts.build_index --embed      # + Gemini 임베딩(GEMINI_API_KEY 필요)
    python -m scripts.build_index --only survey-2025-foreign-report

원천 자료가 바뀌었을 때만 다시 실행한다. 챗봇 요청마다 자료를 다시 읽거나 임베딩하지 않는다.
"""

import argparse
import hashlib
import logging
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.index import build_bm25, save_index, search_text  # noqa: E402
from rag.loaders import load_document  # noqa: E402
from rag.manifest import load_manifest  # noqa: E402
from rag.settings import get_settings  # noqa: E402

logger = logging.getLogger("build_index")


def _file_fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        stat = path.stat()
        digest.update(f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}".encode())
    return digest.hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser(description="Soulrip RAG 인덱스 빌드")
    parser.add_argument("--embed", action="store_true", help="Gemini 임베딩을 함께 계산한다")
    parser.add_argument("--only", nargs="*", help="지정한 manifest 문서 id만 빌드한다(점검용)")
    parser.add_argument("--today", type=date.fromisoformat, help="문화행사 만료 기준일(기본: 오늘)")
    parser.add_argument("--data-dir", type=Path, help="원천 자료 경로(기본: rag-server/data)")
    parser.add_argument("--index-dir", type=Path, help="인덱스 출력 경로(기본: rag-server/index)")
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # Windows 콘솔(cp949)에서 한글 로그 깨짐 방지
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    data_dir = args.data_dir or settings.data_dir
    index_dir = args.index_dir or settings.index_dir

    documents = load_manifest(data_dir)
    if args.only:
        documents = [document for document in documents if document.id in set(args.only)]

    started = time.perf_counter()
    chunks: list[dict] = []
    report = []
    source_paths: list[Path] = []
    for document in documents:
        if not document.index:
            report.append({"id": document.id, "title": document.title, "indexed": False,
                           "reason": document.exclude_reason})
            continue
        doc_started = time.perf_counter()
        produced = list(load_document(document, data_dir, today=args.today))
        source_paths.extend(document.resolve(data_dir))
        chunks.extend(produced)
        report.append({
            "id": document.id,
            "title": document.title,
            "indexed": True,
            "collection": document.collection,
            "year": document.year,
            "audience": document.audience,
            "status": document.status,
            "chunks": len(produced),
            "chars": sum(len(chunk["text"]) for chunk in produced),
        })
        logger.info("%-40s %5d chunks (%.1fs)", document.id, len(produced), time.perf_counter() - doc_started)

    ids = Counter(chunk["id"] for chunk in chunks)
    duplicated = [chunk_id for chunk_id, count in ids.items() if count > 1]
    if duplicated:
        raise SystemExit(f"chunk id가 중복되었습니다: {duplicated[:5]}")

    bm25 = build_bm25(chunks)

    vectors = None
    if args.embed:
        if not settings.gemini_api_key:
            raise SystemExit("--embed에는 GEMINI_API_KEY가 필요합니다.")
        from rag.embeddings import embed_documents

        vectors = embed_documents(
            [search_text(chunk) for chunk in chunks],
            api_key=settings.gemini_api_key,
            model=settings.gemini_embedding_model,
            dimension=settings.embedding_dimension,
        )

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event_cutoff": (args.today or date.today()).isoformat(),
        "source_fingerprint": _file_fingerprint(source_paths),
        "embedding_model": settings.gemini_embedding_model if vectors is not None else None,
        "embedding_dimension": settings.embedding_dimension if vectors is not None else None,
        "documents": report,
        "collections": dict(Counter(chunk["collection"] for chunk in chunks)),
        "terms": len(bm25.vocab),
        "postings": int(len(bm25.doc_ids)),
    }
    save_index(index_dir, chunks, bm25, meta, vectors)
    logger.info(
        "완료: chunks=%d terms=%d postings=%d dense=%s → %s (%.1fs)",
        len(chunks), len(bm25.vocab), len(bm25.doc_ids), vectors is not None, index_dir,
        time.perf_counter() - started,
    )


if __name__ == "__main__":
    main()
