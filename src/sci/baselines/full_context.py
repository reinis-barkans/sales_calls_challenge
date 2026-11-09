"""Baseline 2: all 20 transcripts (~95K tokens) in one prompt-cached system
prompt -> one answer. The quality ceiling at this dataset size; does not scale
past one context window and pays for the whole corpus on every question."""
from __future__ import annotations

from functools import lru_cache

from sci import llm
from sci.baselines.common import BASELINE_RULES, BaselineAnswer, to_answer
from sci.config import STRONG_MODEL
from sci.ingest.parse import load_calls, render_transcript
from sci.models import Answer


@lru_cache
def _corpus() -> str:
    return "\n\n=====\n\n".join(render_transcript(cid) for cid in load_calls())


def ask(question: str) -> Answer:
    system = BASELINE_RULES + "\n\nTRANSCRIPTS:\n\n" + _corpus()
    b = llm.structured(step="full_context", model=STRONG_MODEL, system=system, user=f"Question: {question}",
                       schema=BaselineAnswer, max_tokens=12000, cache_system=True)
    return to_answer(question, b, sorted(load_calls()))
