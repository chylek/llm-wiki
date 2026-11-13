#!/usr/bin/env python3
"""Semantic search over the knowledge base with local embeddings (Ollama + Chroma).

Why: grep finds notes that share *words* with a query. Embeddings find notes
that share *meaning* ("heat pump noise" -> a note titled "Night-time
compressor limits"). Both run locally: Ollama computes the vectors, Chroma
stores them on disk under ``.index/`` (gitignored), nothing leaves the machine.

How:
* Notes are split into chunks at ``## `` headings, so a long note can match
  on the one section that is relevant.
* Each chunk's id is ``<file>::<heading>`` and its metadata stores a SHA-256
  of the text; ``reindex`` only re-embeds chunks whose hash changed and
  deletes chunks whose source disappeared. Run it from cron (nightly is fine).
* ``query`` ranks by cosine similarity, keeps the best chunk per file, and
  drops weak matches below ``MIN_SIMILARITY``.

usage:
    scripts/vector_index.py reindex
    scripts/vector_index.py query "some question" [n]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import chromadb
import requests
from chromadb import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / ".index" / "chroma"
COLLECTION_NAME = "knowledge"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
#: bge-m3 is multilingual, so notes in different languages still match.
EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")

DEFAULT_N_RESULTS = 5
#: Tuned by eye: below this, "related" results were mostly noise.
MIN_SIMILARITY = 0.45

FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^## (.+)$")
FENCE_RE = re.compile(r"^```")


# --------------------------------------------------------------------------
# Chunking (pure functions, covered by tests/test_vector_index.py)
# --------------------------------------------------------------------------


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def chunk_markdown(text: str) -> list[tuple[str, str]]:
    """Split a note into (label, text) chunks at level-2 headings.

    A note without ``## `` headings is one ``(whole)`` chunk; text before the
    first heading is ``(intro)``. Headings inside fenced code are ignored,
    and repeated headings get a ``(2)``, ``(3)`` suffix so ids stay unique.
    """
    body = strip_frontmatter(text).strip()
    if not body:
        return []

    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    in_fence = False
    for line in body.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        heading = None if in_fence else HEADING_RE.match(line)
        if heading:
            sections.append((heading.group(1).strip(), []))
        else:
            sections[-1][1].append(line)

    if len(sections) == 1:
        return [("(whole)", body)]

    chunks: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for heading, lines in sections:
        content = "\n".join(lines).strip()
        if not content:
            continue
        if heading is None:
            chunks.append(("(intro)", content))
            continue
        seen[heading] = seen.get(heading, 0) + 1
        label = heading if seen[heading] == 1 else f"{heading} ({seen[heading]})"
        chunks.append((label, f"## {heading}\n\n{content}"))
    return chunks


def iter_source_files(root: Path) -> list[Path]:
    """Every note that should be searchable: knowledge/, memory/, raw/ (minus READMEs)."""
    files = [p for top in ("knowledge", "memory", "raw") for p in (root / top).rglob("*.md")]
    return sorted(p for p in files if p.name != "README.md")


# --------------------------------------------------------------------------
# Chroma + Ollama
# --------------------------------------------------------------------------


class OllamaEmbeddingFunction(EmbeddingFunction):
    """Chroma calls this with a batch of texts; Ollama's /api/embed returns their vectors."""

    def __init__(self, model: str = EMBED_MODEL, base_url: str = OLLAMA_URL) -> None:
        self.model = model
        self.base_url = base_url

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - name fixed by Chroma
        resp = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": list(input)},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    @staticmethod
    def name() -> str:
        return "ollama"


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(INDEX_DIR), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=OllamaEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},  # distance = 1 - cosine similarity
    )


def reindex(collection: chromadb.Collection, root: Path) -> tuple[int, int]:
    """Incrementally sync the index with the files -> (chunks seen, stale chunks removed)."""
    seen_ids: set[str] = set()
    for path in iter_source_files(root):
        rel = str(path.relative_to(root))
        for heading, text in chunk_markdown(path.read_text(encoding="utf-8")):
            cid = f"{rel}::{heading}"
            seen_ids.add(cid)
            digest = hashlib.sha256(text.encode()).hexdigest()
            existing = collection.get(ids=[cid], include=["metadatas"])
            if existing["ids"] and existing["metadatas"][0].get("hash") == digest:
                continue  # unchanged: skip the embedding call
            collection.upsert(
                ids=[cid], documents=[text], metadatas=[{"file": rel, "heading": heading, "hash": digest}]
            )
    stale = [cid for cid in collection.get(include=[])["ids"] if cid not in seen_ids]
    if stale:
        collection.delete(ids=stale)
    return len(seen_ids), len(stale)


def query(collection: chromadb.Collection, text: str, n: int = DEFAULT_N_RESULTS) -> list[tuple[str, float]]:
    """Top ``n`` files by their best-matching chunk -> [(path, similarity)]."""
    # Over-fetch chunks: several may belong to the same file.
    n_results = max(1, min(collection.count(), max(n * 10, 50)))
    res = collection.query(query_texts=[text], n_results=n_results)
    best: dict[str, float] = {}
    for distance, meta in zip(res["distances"][0], res["metadatas"][0], strict=True):
        best[meta["file"]] = max(best.get(meta["file"], 0.0), 1 - distance)
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    return [(f, s) for f, s in ranked if s >= MIN_SIMILARITY][:n]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("reindex")
    q = sub.add_parser("query")
    q.add_argument("text")
    q.add_argument("n", nargs="?", type=int, default=DEFAULT_N_RESULTS)
    args = parser.parse_args(argv)

    # Every failure is reported on stderr with exit 1: search.sh treats that
    # as "semantic layer unavailable" and carries on without it.
    try:
        collection = get_collection()
        if args.command == "reindex":
            seen, stale = reindex(collection, REPO_ROOT)
            print(f"indexed {seen} chunk(s), removed {stale} stale chunk(s)")
        else:
            for file, sim in query(collection, args.text, args.n):
                print(f"{file}\t{sim:.3f}")
    except Exception as exc:  # noqa: BLE001 - any backend error means "unavailable"
        print(f"vector search unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
