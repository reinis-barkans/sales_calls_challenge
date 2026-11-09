"""BM25 keyword index over chunks, enriched with the normalised statements of
extracted facts that fall in each chunk (so a search for '£1,800' can hit a chunk
where the customer said 'eighteen hundred a month').

Plus a dense index (bge-small-en-v1.5 via fastembed/ONNX, local, no API key)
for matches on meaning that share no keywords ("too expensive" ~ "pricing").
Chunk vectors are cached in artifacts/ keyed by a hash of the chunk texts.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache

import numpy as np

from rank_bm25 import BM25Okapi

from sci.config import ARTIFACTS, BM25_TOP_CHUNKS, EMBED_MODEL
from sci.ingest.chunk import build_chunks
from sci.models import Chunk

_STOP = set("""a an the and or of to in on for with at by from is are was were be been it its this that
these those what which who whom how why when where did do does any anyone has have had about their
there they them our we you your i me my as but not no so if than then into over can could would should
said say says customers customer prospects prospect calls call""".split())
_TOKEN = re.compile(r"[a-z0-9£$][a-z0-9£$.\-]*")


def tokenize(s: str) -> list[str]:
    toks = [t.strip(".-") for t in _TOKEN.findall(s.lower())]
    return [t for t in toks if t and t not in _STOP]


def _fact_text_by_turn() -> dict[str, str]:
    from sci.ingest.extract import load_facts  # lazy: facts may not exist yet
    out: dict[str, list[str]] = {}
    for f in load_facts():
        for tid in f.turn_ids:
            out.setdefault(tid, []).append(f"{f.entity} {f.statement}")
    return {k: " ".join(v) for k, v in out.items()}


class ChunkIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        facts = _fact_text_by_turn()
        docs = []
        for c in chunks:
            enrich = " ".join(facts.get(t, "") for t in c.turn_ids)
            docs.append(tokenize(c.text + " " + enrich))
        self.bm25 = BM25Okapi(docs)

    def search(self, query: str, k: int = BM25_TOP_CHUNKS, call_ids: set[str] | None = None) -> list[tuple[Chunk, float]]:
        q = tokenize(query)
        if not q:
            return []
        scores = self.bm25.get_scores(q)
        ranked = sorted(range(len(self.chunks)), key=lambda i: -scores[i])
        out = []
        for i in ranked:
            if scores[i] <= 0:
                break
            if call_ids and self.chunks[i].call_id not in call_ids:
                continue
            out.append((self.chunks[i], float(scores[i])))
            if len(out) >= k:
                break
        return out


@lru_cache
def _embedder():
    from fastembed import TextEmbedding
    return TextEmbedding(EMBED_MODEL)


def embed(texts: list[str]) -> np.ndarray:
    vecs = np.array(list(_embedder().embed(texts)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


class VectorIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        digest = hashlib.sha256(json.dumps([EMBED_MODEL] + [c.text for c in chunks]).encode()).hexdigest()[:16]
        path = ARTIFACTS / f"chunk_vectors_{digest}.npy"
        if path.exists():
            self.vecs = np.load(path)
        else:
            self.vecs = embed([c.text for c in chunks])
            ARTIFACTS.mkdir(parents=True, exist_ok=True)
            for old in ARTIFACTS.glob("chunk_vectors_*.npy"):
                old.unlink()
            np.save(path, self.vecs)

    def search(self, query: str, k: int, call_ids: set[str] | None = None) -> list[tuple[Chunk, float]]:
        sims = self.vecs @ embed([query])[0]
        out = []
        for i in np.argsort(-sims):
            if call_ids and self.chunks[i].call_id not in call_ids:
                continue
            out.append((self.chunks[i], float(sims[i])))
            if len(out) >= k:
                break
        return out


@lru_cache
def get_vector_index() -> VectorIndex:
    return VectorIndex(build_chunks())


@lru_cache
def get_index() -> ChunkIndex:
    return ChunkIndex(build_chunks())
