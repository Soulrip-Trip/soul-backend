"""BM25 역색인 빌드·저장·로드.

저장 형식(index/)
- chunks.jsonl.gz : chunk 본문과 메타데이터
- vocab.json      : 용어 목록(배열 위치 = term id)
- bm25.npz        : CSR 형태 postings(term_offsets, doc_ids, tfs)와 문서 길이
- vectors.npy     : (선택) 정규화된 dense 임베딩. --embed로 빌드했을 때만 존재
- meta.json       : 빌드 시각, 문서·chunk 수, 원천 자료 목록

postings를 파이썬 list가 아닌 numpy 배열로 저장해 메모리 사용량과 로드 시간을 줄인다.
"""

import gzip
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rag import INDEX_FORMAT_VERSION
from rag.text import tokenize

CHUNKS_FILE = "chunks.jsonl.gz"
VOCAB_FILE = "vocab.json"
BM25_FILE = "bm25.npz"
VECTORS_FILE = "vectors.npy"
META_FILE = "meta.json"


def search_text(chunk: dict) -> str:
    """색인 대상 문자열. 제목·위치를 함께 넣어 '2025', '외국인' 같은 메타 단어도 검색되게 한다."""
    return f"{chunk['title']}\n{chunk['location']}\n{chunk['text']}"


@dataclass
class Bm25Arrays:
    vocab: dict[str, int]
    term_offsets: np.ndarray
    doc_ids: np.ndarray
    tfs: np.ndarray
    doc_len: np.ndarray

    @property
    def avg_doc_len(self) -> float:
        return float(self.doc_len.mean()) if len(self.doc_len) else 0.0


def build_bm25(chunks: list[dict]) -> Bm25Arrays:
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    doc_len = np.zeros(len(chunks), dtype=np.float32)
    for index, chunk in enumerate(chunks):
        counts = Counter(tokenize(search_text(chunk)))
        doc_len[index] = sum(counts.values())
        for term, tf in counts.items():
            postings[term].append((index, tf))

    terms = sorted(postings)
    total = sum(len(postings[term]) for term in terms)
    term_offsets = np.zeros(len(terms) + 1, dtype=np.int64)
    doc_ids = np.empty(total, dtype=np.int32)
    tfs = np.empty(total, dtype=np.float32)
    cursor = 0
    for term_id, term in enumerate(terms):
        items = postings[term]
        doc_ids[cursor:cursor + len(items)] = [doc for doc, _ in items]
        tfs[cursor:cursor + len(items)] = [tf for _, tf in items]
        cursor += len(items)
        term_offsets[term_id + 1] = cursor

    return Bm25Arrays(
        vocab={term: term_id for term_id, term in enumerate(terms)},
        term_offsets=term_offsets,
        doc_ids=doc_ids,
        tfs=tfs,
        doc_len=doc_len,
    )


def save_index(
    index_dir: Path,
    chunks: list[dict],
    bm25: Bm25Arrays,
    meta: dict,
    vectors: np.ndarray | None = None,
) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(index_dir / CHUNKS_FILE, "wt", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False, separators=(",", ":")) + "\n")

    terms = [""] * len(bm25.vocab)
    for term, term_id in bm25.vocab.items():
        terms[term_id] = term
    (index_dir / VOCAB_FILE).write_text(json.dumps(terms, ensure_ascii=False), encoding="utf-8")

    np.savez_compressed(
        index_dir / BM25_FILE,
        term_offsets=bm25.term_offsets,
        doc_ids=bm25.doc_ids,
        tfs=bm25.tfs,
        doc_len=bm25.doc_len,
    )

    vector_path = index_dir / VECTORS_FILE
    if vectors is not None:
        np.save(vector_path, vectors.astype(np.float32))
    elif vector_path.exists():
        vector_path.unlink()  # 이전 빌드의 임베딩이 다른 chunk 순서와 섞이지 않도록 제거

    meta = {**meta, "format_version": INDEX_FORMAT_VERSION, "chunks": len(chunks), "dense": vectors is not None}
    (index_dir / META_FILE).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_index(index_dir: Path) -> tuple[list[dict], Bm25Arrays, dict, np.ndarray | None]:
    meta = json.loads((index_dir / META_FILE).read_text(encoding="utf-8"))
    if meta.get("format_version") != INDEX_FORMAT_VERSION:
        raise ValueError(
            f"인덱스 형식 버전이 다릅니다(index={meta.get('format_version')}, code={INDEX_FORMAT_VERSION}). "
            "scripts/build_index.py로 다시 빌드하세요."
        )

    with gzip.open(index_dir / CHUNKS_FILE, "rt", encoding="utf-8") as file:
        chunks = [json.loads(line) for line in file if line.strip()]

    terms = json.loads((index_dir / VOCAB_FILE).read_text(encoding="utf-8"))
    with np.load(index_dir / BM25_FILE) as arrays:  # allow_pickle=False(기본값)
        bm25 = Bm25Arrays(
            vocab={term: term_id for term_id, term in enumerate(terms)},
            term_offsets=arrays["term_offsets"],
            doc_ids=arrays["doc_ids"],
            tfs=arrays["tfs"],
            doc_len=arrays["doc_len"],
        )

    vectors = None
    vector_path = index_dir / VECTORS_FILE
    if vector_path.exists():
        vectors = np.load(vector_path)
        if len(vectors) != len(chunks):
            raise ValueError("vectors.npy와 chunks 수가 다릅니다. 인덱스를 다시 빌드하세요.")

    if len(bm25.doc_len) != len(chunks):
        raise ValueError("bm25.npz와 chunks 수가 다릅니다. 인덱스를 다시 빌드하세요.")
    return chunks, bm25, meta, vectors
