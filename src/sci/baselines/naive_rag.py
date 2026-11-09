"""Baseline 1: classic RAG. Top-k BM25 chunks -> one answer prompt. No call
picking, no per-call reading, no verifier."""
from __future__ import annotations

from sci import llm
from sci.baselines.common import BASELINE_RULES, BaselineAnswer, to_answer
from sci.config import STRONG_MODEL
from sci.ingest.index import get_index
from sci.ingest.parse import load_turns
from sci.models import Answer

K = 8


def ask(question: str) -> Answer:
    hits = get_index().search(question, k=K)
    blocks = []
    for chunk, _ in hits:
        turns = {t.turn_id: t for t in load_turns()[chunk.call_id]}
        body = "\n".join(f"{tid.split('#')[1]} [{turns[tid].ts}] {turns[tid].speaker} ({turns[tid].side}): {turns[tid].text}"
                         for tid in chunk.turn_ids)
        blocks.append(f"--- {chunk.text.splitlines()[0]}\n{body}")
    user = f"Transcript excerpts:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"
    b = llm.structured(step="naive_rag", model=STRONG_MODEL, system=BASELINE_RULES, user=user,
                       schema=BaselineAnswer, max_tokens=12000)
    return to_answer(question, b, sorted({c.call_id for c, _ in hits}))
