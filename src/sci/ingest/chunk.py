"""Turn-window chunks: replies only make sense next to the question they answer,
and citations need turn boundaries anyway, so we window by turns, not tokens."""
from __future__ import annotations

from functools import lru_cache

from sci.config import CHUNK_OVERLAP, CHUNK_TURNS
from sci.ingest.parse import load_calls, load_turns
from sci.models import Chunk


@lru_cache
def build_chunks() -> list[Chunk]:
    calls = load_calls()
    chunks: list[Chunk] = []
    step = CHUNK_TURNS - CHUNK_OVERLAP
    for cid, turns in load_turns().items():
        c = calls[cid]
        header = f"{cid} | {c.company} | {c.category} | {c.stage}"
        for start in range(0, max(len(turns) - CHUNK_OVERLAP, 1), step):
            window = turns[start:start + CHUNK_TURNS]
            body = "\n".join(f"[{t.ts}] {t.speaker} ({t.side}): {t.text}" for t in window)
            chunks.append(Chunk(
                chunk_id=f"{window[0].turn_id}-{window[-1].turn_id.split('#')[1]}",
                call_id=cid, turn_ids=[t.turn_id for t in window], text=f"{header}\n{body}",
            ))
    return chunks
